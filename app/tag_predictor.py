import pandas as pd
import torch

ML_MODEL_PATH = "./model/michelin_model"
import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification


class TagPredictor:
    """
    Manages the prediction of tags for input text using a machine learning model.

    This class is responsible for loading a pre-trained machine learning model and its
    associated resources, including a tokenizer, label definitions, and threshold values.
    It uses the model to process input text and predicts relevant tags with their associated
    probabilities, providing an inference API for text tagging tasks.

    Attributes:
        model_path (str): Path to the directory containing the pre-trained model files.
        model: The machine learning model used for sequence classification tasks.
        tokenizer: Tokenizer used to preprocess input text for the model.
        label_names (list of str): List of tag labels used by the model.
        threshold (float): Probability threshold for classifying a tag as relevant.
        available (bool): Indicates whether the model and resources are successfully loaded.
    """

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

    def _load_model(self) -> None:
        """
        Loads the machine learning model, tokenizer, and necessary configuration
        from the specified model path. This method initializes the tokenizer,
        loads the model for sequence classification, reads the label names, and
        sets the classification threshold. Ensures the model and required files
        are properly loaded for subsequent inference tasks.

        Raises:
            FileNotFoundError: If the specified model path does not exist.
        """
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

    def predict_tags(self, query_text) -> dict:
        """
        Predicts relevant tags for a given query text based on the trained model's output.

        This method processes the input text using the tokenizer and evaluates it using
        the model to produce tag probabilities. Tags with probabilities exceeding the
        defined threshold are included in the result. If the model is unavailable or an
        error occurs during execution, an empty dictionary is returned.

        Args:
            query_text: A string representing the input text for which tags are predicted.

        Returns:
            A dictionary where keys are the predicted tag names (str) and values are their
            associated probabilities (float). Returns an empty dictionary if the model is
            unavailable or an error occurs.
        """
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
