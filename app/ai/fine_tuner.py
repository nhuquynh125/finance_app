# fine_tuner.py  (cập nhật: lưu model vào thư mục AI per-user)
"""
Fine-tune DistilGPT2 với dữ liệu Q&A tài chính sinh ra từ database của user.

Thay đổi: MODEL_DIR lấy động từ user_session.session.ai_dir
"""

from pathlib import Path
from app.data.models import get_connection


def _get_model_dir() -> Path:
    """Thư mục lưu fine-tuned model của user hiện tại."""
    try:
        from user_session import session
        if session.is_logged_in:
            return session.ai_dir / "fine_tuned_model"
    except ImportError:
        pass
    try:
        from config import DATA_DIR
        return Path(DATA_DIR) / "fine_tuned_model"
    except ImportError:
        return Path("data") / "fine_tuned_model"


def generate_training_data() -> list:
    """Tạo dataset Q&A từ giao dịch thực trong DB của user hiện tại."""
    with get_connection() as conn:
        summary_rows = conn.execute("""
            SELECT strftime('%Y-%m', date) as month,
                   SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) as income,
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
            FROM transactions
            WHERE amount > 0
            GROUP BY month ORDER BY month DESC LIMIT 12
        """).fetchall()

        cat_rows = conn.execute("""
            SELECT c.name, SUM(t.amount) as total,
                   strftime('%Y-%m', t.date) as month
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense' AND t.amount > 0
              AND t.description IS NOT NULL AND t.description != ''
            GROUP BY c.id, month
            ORDER BY month DESC LIMIT 60
        """).fetchall()

    samples = []

    for row in summary_rows:
        month   = row["month"]
        income  = row["income"]  or 0
        expense = row["expense"] or 0
        saving  = income - expense

        samples += [
            {
                "prompt":   f"Thang {month} toi thu nhap bao nhieu?",
                "response": f"Thang {month} ban co thu nhap {income:,.0f} dong."
            },
            {
                "prompt":   f"Toi chi tieu bao nhieu thang {month}?",
                "response": f"Thang {month} ban da chi {expense:,.0f} dong."
            },
            {
                "prompt":   f"Thang {month} toi tiet kiem duoc khong?",
                "response": (
                    f"Thang {month} ban tiet kiem duoc {saving:,.0f} dong "
                    f"({saving / income * 100:.1f}% thu nhap)."
                    if income > 0 and saving > 0
                    else
                    f"Thang {month} ban chi vuot thu nhap {abs(saving):,.0f} dong."
                )
            },
        ]

    for row in cat_rows:
        samples.append({
            "prompt":   f"Thang {row['month']} toi chi cho {row['name']} bao nhieu?",
            "response": f"Thang {row['month']} ban chi {row['total']:,.0f} dong cho {row['name']}.",
        })

    # Kiến thức tài chính chung
    samples += [
        {"prompt": "Nguyen tac 50-30-20 la gi?",
         "response": "50% cho nhu cau thiet yeu, 30% cho mong muon, 20% de tiet kiem va dau tu."},
        {"prompt": "Quy khan cap la gi?",
         "response": "Quy khan cap la khoan tien du phong cho tinh huong bat ngo, nen co 3-6 thang chi phi sinh hoat."},
        {"prompt": "Lam sao giam chi tieu an uong?",
         "response": "Nau an tai nha, lap ke hoach bua an truoc, tranh order food thuong xuyen, mua sam theo danh sach."},
        {"prompt": "Toi nen dat ngan sach an uong bao nhieu?",
         "response": "Chi phi an uong nen chiem khoang 15-25% thu nhap hang thang."},
        {"prompt": "The tin dung co nen dung khong?",
         "response": "The tin dung tot neu ban tra het so du moi thang, tranh de no tich luy vi lai suat cao 20-30%/nam."},
        {"prompt": "Lam sao theo doi chi tieu hieu qua?",
         "response": "Ghi lai moi khoan chi ngay sau khi chi, phan loai ro rang, xem bao cao cuoi thang de dieu chinh."},
    ]

    return samples


def fine_tune_model(epochs: int = 3,
                    progress_callback=None) -> str:
    """
    Fine-tune DistilGPT2 với dữ liệu của user hiện tại.
    Lưu model vào thư mục AI per-user.
    Trả về đường dẫn thư mục model đã lưu.
    """
    try:
        from transformers import (
            GPT2Tokenizer, GPT2LMHeadModel,
            Trainer, TrainingArguments,
            DataCollatorForLanguageModeling
        )
        from datasets import Dataset
        import torch
    except ImportError:
        raise ImportError(
            "Cài thư viện: pip install transformers datasets torch accelerate"
        )

    model_dir = _get_model_dir()

    if progress_callback:
        progress_callback("Tạo dữ liệu huấn luyện từ database...")

    samples = generate_training_data()
    if len(samples) < 5:
        raise ValueError(
            "Chưa đủ dữ liệu. Thêm giao dịch vào app trước khi train."
        )

    if progress_callback:
        progress_callback(f"Chuẩn bị {len(samples)} mẫu huấn luyện...")

    texts = [
        f"Hoi: {s['prompt']}\nTra loi: {s['response']}<|endoftext|>"
        for s in samples
    ]

    model_name = "distilgpt2"
    tokenizer  = GPT2Tokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token
    model      = GPT2LMHeadModel.from_pretrained(model_name)

    def tokenize(examples):
        tokens = tokenizer(
            examples["text"],
            truncation=True,
            max_length=256,
            padding="max_length",
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    dataset = Dataset.from_dict({"text": texts})
    dataset = dataset.map(tokenize, batched=True, remove_columns=["text"])

    if progress_callback:
        progress_callback("Bắt đầu huấn luyện model...")

    model_dir.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir                  = str(model_dir),
        num_train_epochs            = epochs,
        per_device_train_batch_size = 4,
        save_steps                  = 9999,
        save_total_limit            = 1,
        logging_steps               = 10,
        learning_rate               = 5e-5,
        warmup_steps                = 20,
        fp16                        = torch.cuda.is_available(),
        no_cuda                     = not torch.cuda.is_available(),
        report_to                   = "none",
    )

    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model         = model,
        args          = args,
        train_dataset = dataset,
        data_collator = collator,
    )

    if progress_callback:
        progress_callback(
            f"Đang train {epochs} epoch với {len(texts)} mẫu...\n"
            "(Có thể mất 5-15 phút tùy máy tính)")

    trainer.train()
    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))

    if progress_callback:
        progress_callback("Huấn luyện hoàn tất!")

    return str(model_dir)
