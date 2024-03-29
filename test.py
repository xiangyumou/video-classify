import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report
from dataset import VideoFrameDataset  # Custom dataset module.
from models import r3d_18, r2plus1d_18  # Custom models module.
import seaborn as sns
import warnings
import numpy as np

warnings.filterwarnings("ignore")  # Suppress warnings for cleaner output.


# Function to evaluate the model on the test dataset.
def evaluate(model, dataloader, device):
    all_label = []
    all_pred = []
    acc_label = []
    acc_pred = []

    with torch.no_grad():  # No gradient calculation to save memory and computations.
        for batch_idx, data in enumerate(dataloader):
            # Get the inputs and labels from the data loader.
            inputs, labels = data['data'].to(device), data['label'].to(device)
            # Forward pass through the model.
            outputs = model(inputs)
            if isinstance(outputs, list):
                outputs = outputs[0]
            # Collect predictions and labels for later analysis.
            prediction = torch.max(outputs, 1)[1]
            all_label.extend(labels.squeeze())
            all_pred.extend(prediction)
            acc_label.extend(labels.squeeze().cpu().numpy())
            acc_pred.extend(prediction.cpu().numpy())

    # Post-processing for classification report.
    all_label = torch.stack(all_label, dim=0)
    all_pred = torch.stack(all_pred, dim=0)
    all_label = all_label.squeeze().cpu().data.squeeze().numpy()
    all_pred = all_pred.cpu().data.squeeze().numpy()
    print(classification_report(all_label, all_pred, digits=3))
    
    # Generating and plotting the confusion matrix.
    cm = confusion_matrix(all_label, all_pred)
    class_names = ['Moving Arms', 'Swing Hands']

    fig, ax = plt.subplots(figsize=(8, 6))
    cax = ax.matshow(cm, cmap=plt.cm.Blues)

    plt.title('Confusion Matrix')
    plt.xlabel('Predicted')
    plt.ylabel('True')

    ax.set_xticklabels([''] + class_names)
    ax.set_yticklabels([''] + class_names)

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), va='center', ha='center', color='black')

    print("Confusion Matrix:")
    print(cm)

    plt.grid(False)
    plt.show()


# Main program settings and data loading.
batch_size = 4
sample_size = 128
sample_duration = 16
num_classes = 2

# Paths for model weights.
model_path = "r3d.pth"
model_name = model_path[:-4]  # Extract model name from file path.
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
torch.manual_seed(2023)

if __name__ == '__main__':
    # Load and preprocess data.
    transform = transforms.Compose([
        transforms.Resize([sample_size, sample_size]),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])
    test_set= VideoFrameDataset(root_dir="data/test", frame_count=sample_duration, transform=transform)

    print("Test Dataset samples: {}".format(len(test_set)))
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=False)

    # Model selection and loading pretrained weights.
    # Uncomment the model you want to use.
    model = r3d_18(num_classes=num_classes).to(device)

    model.load_state_dict(torch.load(model_path))
    model.eval()  # Set model to evaluation mode.

    # Evaluate the model.
    evaluate(model, test_loader, device)
