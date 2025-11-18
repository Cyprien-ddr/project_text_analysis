import warnings

import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset
import torch
import numpy as np
from sklearn.metrics import f1_score, accuracy_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings('ignore')


def get_tags(csv_path='data/michelin_thailand_details.csv'):
    df = pd.read_csv(csv_path)

    tag_column = None
    if 'good_for_tags' in df.columns:
        tag_column = 'good_for_tags'
    elif 'tags' in df.columns:
        tag_column = 'tags'
    else:
        raise ValueError("No 'tags' or 'good_for_tags' column found in CSV")

    df = df.dropna(subset=[tag_column])

    all_tags = []
    for tag_str in df[tag_column]:
        if pd.isna(tag_str) or tag_str == '':
            continue
        tags = [t.strip() for t in str(tag_str).split(';') if t.strip()]
        all_tags.extend(tags)

    unique_tags = sorted(list(set(all_tags)))
    return unique_tags, tag_column


def build_dataset(csv_path='data/michelin_thailand_details.csv'):
    df = pd.read_csv(csv_path)

    if 'description' not in df.columns:
        raise ValueError("No 'description' column found in CSV")

    df = df.dropna(subset=['description'])

    labels_list, tag_column = get_tags(csv_path)
    print(f"Detected {len(labels_list)} unique labels:\n{labels_list}\n")

    if len(labels_list) == 0:
        raise ValueError("No tags found in the dataset. Please check your data.")

    def encode_tags(tag_str):
        vec = [0] * len(labels_list)
        if pd.isna(tag_str) or tag_str == '':
            return vec

        tags = [t.strip() for t in str(tag_str).split(';') if t.strip()]
        if not tags:
            tags = [t.strip() for t in str(tag_str).split(',') if t.strip()]

        for t in tags:
            if t in labels_list:
                vec[labels_list.index(t)] = 1
        return vec

    if tag_column not in df.columns:
        df[tag_column] = ''

    df['label_vector'] = df[tag_column].apply(encode_tags)

    df = df[df['label_vector'].apply(lambda x: sum(x) > 0)]

    print(f"Total samples with labels: {len(df)}")

    if len(df) < 10:
        raise ValueError(f"Not enough samples with labels ({len(df)}). Need at least 10 samples.")

    test_size = 0.2 if len(df) >= 50 else 0.15
    train_df, test_df = train_test_split(df, test_size=test_size, random_state=42)

    print(f"Training samples: {len(train_df)}")
    print(f"Test samples: {len(test_df)}\n")

    train_labels = [[float(x) for x in label] for label in train_df['label_vector'].tolist()]
    test_labels = [[float(x) for x in label] for label in test_df['label_vector'].tolist()]

    train_data = {
        "text": train_df['description'].tolist(),
        "labels": train_labels
    }
    test_data = {
        "text": test_df['description'].tolist(),
        "labels": test_labels
    }

    return Dataset.from_dict(train_data), Dataset.from_dict(test_data), labels_list


def train_multi_label_model(csv_path='data/michelin_thailand_details.csv', epochs=5, batch_size=8, learning_rate=3e-5):
    print("=" * 70)
    print("STARTING TRAINING PIPELINE")
    print("=" * 70 + "\n")

    train_dataset, test_dataset, label_names = build_dataset(csv_path)
    num_labels = len(label_names)

    print("\nLABEL DISTRIBUTION ANALYSIS")
    print("=" * 70)
    df = pd.read_csv(csv_path)
    tag_column = 'good_for_tags' if 'good_for_tags' in df.columns else 'tags'

    label_counts = {label: 0 for label in label_names}
    for tags_str in df[tag_column].dropna():
        tags = [t.strip() for t in str(tags_str).split(';') if t.strip()]
        for tag in tags:
            if tag in label_counts:
                label_counts[tag] += 1

    print("\nTag frequencies:")
    for label, count in sorted(label_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {label:25s}: {count:3d} ({count / len(df) * 100:5.1f}%)")
    print()

    label_counts_array = np.array([label_counts[label] for label in label_names])
    total_samples = label_counts_array.sum()

    pos_weight = torch.tensor(
        [np.sqrt((total_samples - count) / max(count, 1)) for count in label_counts_array],
        dtype=torch.float32
    )

    pos_weight = torch.clamp(pos_weight, min=1.0, max=5.0)

    print(f"\n⚖️  Class weights (dampened, capped at 5.0):")
    for label, weight in zip(label_names, pos_weight):
        print(f"  {label:25s}: {weight:.2f} (n={label_counts[label]})")
    print()

    model_name = "roberta-base"
    print(f"Loading model: {model_name}\n")
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def tokenize(batch):
        enc = tokenizer(batch["text"], truncation=True, padding="max_length", max_length=512)
        enc["labels"] = batch["labels"]
        return enc

    print("Tokenizing datasets...")
    train_dataset = train_dataset.map(tokenize, batched=True)
    test_dataset = test_dataset.map(tokenize, batched=True)

    train_dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    test_dataset.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        problem_type="multi_label_classification",
        num_labels=num_labels
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pos_weight = pos_weight.to(device)
    model.to(device)

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            logits = outputs.logits

            loss_fct = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
            loss = loss_fct(logits, labels)

            return (loss, outputs) if return_outputs else loss

    training_args = TrainingArguments(
        output_dir="./results",
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_dir="./logs",
        logging_steps=20,
        learning_rate=learning_rate,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        save_total_limit=3,
        warmup_steps=50,
        weight_decay=0.01,
        fp16=torch.cuda.is_available(),
    )

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        sigmoid = torch.sigmoid(torch.tensor(logits))

        best_f1_macro = 0
        best_threshold = 0.5

        for threshold in [0.4, 0.45, 0.5, 0.55, 0.6]:
            preds = (sigmoid > threshold).int().numpy()
            labels_int = labels.astype(int)
            f1_macro = f1_score(labels_int, preds, average="macro", zero_division=0)
            if f1_macro > best_f1_macro:
                best_f1_macro = f1_macro
                best_threshold = threshold

        preds = (sigmoid > best_threshold).int().numpy()
        labels = labels.astype(int)

        f1_micro = f1_score(labels, preds, average="micro", zero_division=0)
        f1_macro = f1_score(labels, preds, average="macro", zero_division=0)
        acc = accuracy_score(labels, preds)

        f1_per_label = f1_score(labels, preds, average=None, zero_division=0)

        metrics = {
            "accuracy": acc,
            "f1_micro": f1_micro,
            "f1_macro": f1_macro,
            "best_threshold": best_threshold
        }

        for i, label in enumerate(label_names):
            metrics[f"f1_{label.replace(' ', '_')}"] = f1_per_label[i]

        return metrics

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics
    )

    print("\n" + "=" * 70)
    print("TRAINING STARTED")
    print("=" * 70 + "\n")

    trainer.train()

    print("\n" + "=" * 70)
    print("FINAL EVALUATION")
    print("=" * 70 + "\n")

    eval_results = trainer.evaluate()
    print(f"Final Accuracy: {eval_results['eval_accuracy']:.4f}")
    print(f"Final F1 (micro): {eval_results['eval_f1_micro']:.4f}")
    print(f"Final F1 (macro): {eval_results['eval_f1_macro']:.4f}")
    print(f"Best Threshold: {eval_results.get('eval_best_threshold', 0.5):.2f}")

    print("\n Per-label F1 scores:")
    label_f1_scores = []
    for label in label_names:
        key = f"eval_f1_{label.replace(' ', '_')}"
        if key in eval_results:
            f1_val = eval_results[key]
            label_f1_scores.append((label, f1_val, label_counts[label]))
            print(f"  {label:25s}: {f1_val:.4f} (n={label_counts[label]})")

    print("\n  Labels with low F1 (<0.3):")
    low_f1_labels = [(l, f1, n) for l, f1, n in label_f1_scores if f1 < 0.3]
    if low_f1_labels:
        for label, f1_val, count in low_f1_labels:
            print(f"  {label:25s}: {f1_val:.4f} (only {count} examples)")
    else:
        print("  None! All labels have decent F1 scores.")

    model.save_pretrained("./model/michelin_model")
    tokenizer.save_pretrained("./model/michelin_model")

    label_df = pd.DataFrame({"label": label_names})
    label_df.to_csv("./model/michelin_model/labels.csv", index=False)

    print("\n" + "=" * 70)
    print(" TRAINING COMPLETE")
    print("=" * 70)
    print(f"Model saved in './model/michelin_model'")
    print(f"Labels saved in './model/michelin_model/labels.csv'")

    best_threshold = eval_results.get('eval_best_threshold', 0.5)
    with open("./model/michelin_model/best_threshold.txt", "w") as f:
        f.write(str(best_threshold))
    print(f"Best threshold saved: {best_threshold:.2f}")

    return trainer, label_names, tokenizer, model, best_threshold


def predict_texts(texts, model, tokenizer, label_names, threshold=0.5):

    model.eval()

    device = next(model.parameters()).device

    with torch.no_grad():
        inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=256)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits).cpu().numpy()
        preds = (probs > threshold).astype(int)

    print("\n" + "=" * 70)
    print("PREDICTIONS")
    print("=" * 70 + "\n")

    for i, (text, pred, prob) in enumerate(zip(texts, preds, probs)):
        predicted_tags = []
        for j, val in enumerate(pred):
            if val == 1:
                predicted_tags.append(f"{label_names[j]} ({prob[j]:.2f})")

        print(f"[{i + 1}] Text: {text[:100]}{'...' if len(text) > 100 else ''}")
        print(f"    Tags: {', '.join(predicted_tags) if predicted_tags else 'None'}\n")


def load_and_predict(model_path="./model/michelin_model", texts=None, threshold=0.5):
    print(f"Loading model from {model_path}...")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)

    label_df = pd.read_csv(f"{model_path}/labels.csv")
    label_names = label_df['label'].tolist()

    print(f"Model loaded with {len(label_names)} labels: {label_names}\n")

    if texts:
        predict_texts(texts, model, tokenizer, label_names, threshold)

    return model, tokenizer, label_names, threshold


if __name__ == "__main__":
    import os

    if os.path.exists("./model/michelin_model"):
        print("Model already exists. Loading for predictions...\n")
        model, tokenizer, label_names, threshold = load_and_predict()
    else:
        print("No existing model found. Training new model...\n")
        trainer, label_names, tokenizer, model, threshold = train_multi_label_model(
            csv_path='michelin_thailand_details.csv',
            epochs=5,
            batch_size=8,
            learning_rate=3e-5
        )

    sample_texts = [
        "Beautiful outdoor dining with a farm-to-table experience. Perfect for date nights.",
        "Perfect for groups and family gatherings. Kid-friendly atmosphere.",
        "A trending chef's table that everyone talks about. Worth queueing for.",
        "Solo dining experience with counter seating. Watch the chefs work their magic.",
        "Eat like a local at this iconic neighborhood spot.",
        "I love sport."
    ]

    print("\n" + "=" * 70)
    print("TESTING WITH SAMPLE TEXTS")
    print("=" * 70)
    print(f"\nUsing threshold: {threshold:.2f}\n")

    predict_texts(sample_texts, model, tokenizer, label_names, threshold=threshold)