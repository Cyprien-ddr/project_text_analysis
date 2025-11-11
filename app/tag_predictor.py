import pandas as pd
import torch

ML_MODEL_PATH = "./model/michelin_model"
import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class TagPredictor:

    def __init__(self, model_path=ML_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.label_names = []
        self.threshold = 0.5
        self.available = False

        try:
            self._load_model()
            self.available = True
        except Exception as e:
            print(f"⚠️  ML model not available: {e}")
            print("   Continuing with semantic search only...")

    def _load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model path {self.model_path} not found")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)

        label_df = pd.read_csv(f"{self.model_path}/labels.csv")
        self.label_names = label_df['label'].tolist()

        try:
            with open(f"{self.model_path}/best_threshold.txt", "r") as f:
                self.threshold = float(f.read().strip())
        except:
            self.threshold = 0.5

        self.model.eval()

        print(f"✓ ML model loaded: {len(self.label_names)} tags, threshold={self.threshold:.2f}")

    def predict_tags(self, query_text):
        if not self.available:
            return {}

        try:
            device = next(self.model.parameters()).device

            with torch.no_grad():
                inputs = self.tokenizer(
                    [query_text],
                    return_tensors="pt",
                    truncation=True,
                    padding=True,
                    max_length=256
                )
                inputs = {k: v.to(device) for k, v in inputs.items()}

                outputs = self.model(**inputs)
                probs = torch.sigmoid(outputs.logits).cpu().numpy()[0]

                tag_scores = {}
                for i, (label, prob) in enumerate(zip(self.label_names, probs)):
                    if prob >= self.threshold:
                        tag_scores[label] = float(prob)

                return tag_scores

        except Exception as e:
            print(f"Error in tag prediction: {e}")
            return {}
