import logging
import os
import torch
import torchvision.transforms as transforms
from sklearn.metrics import accuracy_score
from torch import nn, optim
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import torch.nn.functional as F
from dataset import VideoFrameDataset  # Custom dataset for video frames.
from models import r3d_18, r2plus1d_18  # Custom models (3D ResNet and R(2+1)D).
import warnings
warnings.filterwarnings("ignore")  # Ignore warnings for cleaner output.

# Function for training one epoch.
def train_epoch(model, criterion, optimizer, dataloader, device, epoch, logger, writer):
    model.train()  # Set the model to training mode.
    losses = []
    all_label = []
    all_pred = []

    print("train in device:" + str(device))

    for data in tqdm(dataloader):  # Progress bar for batches.
        inputs, labels = data['data'].to(device), data['label'].to(device)
        # print(inputs.shape)
        optimizer.zero_grad()  # Zero the gradients.

        # Forward pass.
        outputs = model(inputs)
        if isinstance(outputs, list):
            outputs = outputs[0]
        
        # Compute loss.
        loss = criterion(outputs, labels.squeeze())
        losses.append(loss.item())

        # Compute accuracy.
        prediction = torch.max(outputs, 1)[1]
        all_label.extend(labels.squeeze())
        all_pred.extend(prediction)
        score = accuracy_score(labels.squeeze().cpu().data.squeeze().numpy(), prediction.cpu().data.squeeze().numpy())

        # Backward pass and optimize.
        loss.backward()
        optimizer.step()

    # Compute the average loss & accuracy for the epoch.
    training_loss = sum(losses) / len(losses)
    all_label = torch.stack(all_label, dim=0)
    all_pred = torch.stack(all_pred, dim=0)
    training_acc = accuracy_score(all_label.squeeze().cpu().data.squeeze().numpy(), all_pred.cpu().data.squeeze().numpy())

    # Logging to TensorBoard and logger.
    writer.add_scalars('Loss', {'train': training_loss}, epoch + 1)
    writer.add_scalars('Accuracy', {'train': training_acc}, epoch + 1)
    logger.info("Average Training Loss of Epoch {}: {:.6f} | Acc: {:.2f}%".format(epoch + 1, training_loss, training_acc * 100))

# Function for validating one epoch.
def val_epoch(model, criterion, dataloader, device, epoch, logger, writer):
    model.eval()  # Set the model to evaluation mode.
    losses = []
    all_label = []
    all_pred = []

    with torch.no_grad():  # Disable gradient calculation.
        for batch_idx, data in enumerate(dataloader):
            inputs, labels = data['data'].to(device), data['label'].to(device)
            outputs = model(inputs)
            if isinstance(outputs, list):
                outputs = outputs[0]
            # outputs = F.softmax(outputs,dim=-1)
            loss = criterion(outputs, labels.squeeze())
            losses.append(loss.item())
            prediction = torch.max(outputs, 1)[1]
            all_label.extend(labels.squeeze())
            all_pred.extend(prediction)

    # Compute the average loss & accuracy for the epoch.
    validation_loss = sum(losses) / len(losses)
    all_label = torch.stack(all_label, dim=0)
    all_pred = torch.stack(all_pred, dim=0)

    validation_acc = accuracy_score(all_label.squeeze().cpu().data.squeeze().numpy(), all_pred.cpu().data.squeeze().numpy())

    # Logging to TensorBoard and logger.
    writer.add_scalars('Loss', {'test': validation_loss}, epoch + 1)
    writer.add_scalars('Accuracy', {'test': validation_acc}, epoch + 1)
    logger.info("Average Testing Loss of Epoch {}: {:.6f} | Acc: {:.2f}%".format(epoch + 1, validation_loss, validation_acc * 100))

    return validation_acc

# Setting paths for data and logs.

sum_path = "r3d"
log_path = "logs/r3d.log"

# Setting up logging to file and TensorBoard.
logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.FileHandler(log_path), logging.StreamHandler()])
logger = logging.getLogger('SLR')
writer = SummaryWriter(sum_path)

# GPU configuration.
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Hyperparameters.
num_classes = 2
epochs = 36
batch_size = 4
learning_rate = 1e-6 
sample_size = 128
sample_duration = 16  # Frame sampling duration.

torch.manual_seed(2023)

if __name__ == '__main__':
    # Data loading and preprocessing.
    transform = transforms.Compose([
        transforms.Resize([sample_size, sample_size]),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])
    train_set = VideoFrameDataset(root_dir="data/train", frame_count=sample_duration, transform=transform)
    val_set = VideoFrameDataset(root_dir="data/test", frame_count=sample_duration, transform=transform)
    logger.info("Dataset samples: {}".format(len(train_set) + len(val_set)))
    logger.info("Training samples: {}".format(len(train_set)))
    logger.info("Test samples: {}".format(len(val_set)))
    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=False)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=False)

    # Model selection and preparation.
    model = r3d_18(pretrained=True, num_classes=num_classes).to(device)

    # Loss criterion and optimizer setup.
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # Training and validation loop.
    logger.info("Training Started".center(60, '#'))
    best_acc = 0.0
    for epoch in range(epochs):
        train_epoch(model, criterion, optimizer, train_loader, device, epoch, logger, writer)
        validation_acc = val_epoch(model, criterion, val_loader, device, epoch, logger, writer)
        # Save the model if it has the best accuracy so far.
        if best_acc < validation_acc:
            best_acc = validation_acc
            torch.save(model.state_dict(), "r3d.pth")
        logger.info("Epoch {} Model Saved".format(epoch + 1).center(60, '#'))

    logger.info("Training Finished".center(60, '#'))
