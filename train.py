# train.py
#!/usr/bin/env	python3

""" train network using pytorch

author baiyu
"""

#import argparse
import os
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms

from torch.utils.data import DataLoader
from dataset import *
from torch.autograd import Variable

from tensorboardX import SummaryWriter
from settings import *

#parser = argparse.ArgumentParser(description='image classification with Pytorch')
#parser.add_argument('--')


#data preprocessing:
transform_train = transforms.Compose([
    transforms.ToPILImage(),
    transforms.RandomCrop(32, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ToTensor(),
    transforms.Normalize(g_cifar100_mean, g_cifar100_std)
])
cifar100_training = CIFAR100Train(g_cifar100_path, transform=transform_train)
cifar100_training_loader = DataLoader(cifar100_training, shuffle=True, num_workers=2, batch_size=16)

transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(g_cifar100_mean, g_cifar100_std)
])
cifar100_test = CIFAR100Test(g_cifar100_path, transform=transform_test)
cifar100_test_loader = DataLoader(cifar100_test, shuffle=True, num_workers=2, batch_size=16)



#from models.resnet import *
#net = resnet101().cuda()

#from models.vgg import *
#net = vgg16_bn().cuda()

#from models.densenet import *
##net = densenet121().cuda()
##net = densenet161().cuda()
#net = densenet201().cuda()

#from models.googlenet import *
#net = GoogleNet().cuda()

from models.rir import *
net = resnet_in_resnet().cuda()


loss_function = nn.CrossEntropyLoss()
optimizer = optim.SGD(net.parameters(), lr=0.1, momentum=0.9, weight_decay=1e-4)
#optimizer = optim.Adam(net.parameters(), lr=0.5, weight_decay=1e-4)
scheduler = optim.lr_scheduler.MultiStepLR(optimizer, milestones=[100, 140], gamma=0.1) #learning rate decay


def train(epoch):
    net.train()

    for batch_index, (labels, images) in enumerate(cifar100_training_loader):

        images = Variable(images)
        labels = Variable(labels)

        labels = labels.cuda()
        images = images.cuda()

        optimizer.zero_grad()
        outputs = net(images)
        loss = loss_function(outputs, labels)
        loss.backward()
        optimizer.step()

        n_iter = (epoch - 1) * len(cifar100_training_loader) + batch_index + 1

        last_layer = list(net.children())[-1]
        for name, para in last_layer.named_parameters():
            if 'weight' in name:
                writer.add_scalar('Gradients/grad_norm2_weights', para.grad.norm(), n_iter)
            if 'bias' in name:
                writer.add_scalar('Gradients/grad_norm2_bias', para.grad.norm(), n_iter)

        print('Training Epoch: {epoch} [{trained_samples}/{total_samples}]\tLoss: {:0.4f}\t'.format(
            loss.data[0],
            epoch=epoch,
            trained_samples=batch_index * len(images),
            total_samples=len(cifar100_training)
        ))

        #update training loss for each iteration
        writer.add_scalar('Train/loss', loss.data[0], n_iter)

    for name, param in net.named_parameters():
        layer, attr = os.path.splitext(name)
        attr = attr[1:]
        writer.add_histogram("{}/{}".format(layer, attr), param, epoch)

def eval_training(epoch):
    net.eval()

    test_loss = 0.0 # cost function error
    correct = 0.0

    for (labels, images) in cifar100_test_loader:
        images = Variable(images)
        labels = Variable(labels)

        images = images.cuda()
        labels = labels.cuda()

        outputs = net(images)
        loss = loss_function(outputs, labels)
        test_loss += loss.data[0]
        _, preds = outputs.max(1)
        correct += preds.eq(labels).sum()

    print(test_loss / len(cifar100_test))
    print('Test set: Average loss: {:.4f}, Accuracy: {:.4f}'.format(
        test_loss / len(cifar100_test),
        correct.float() / len(cifar100_test)
    ))
    print()

    #add informations to tensorboard
    writer.add_scalar('Test/Average loss', test_loss / len(cifar100_test), epoch)
    writer.add_scalar('Test/Accuracy', correct / len(cifar100_test), epoch)

    return correct / len(cifar100_test)

def main():
    #use tensorboard
    if not os.path.exists('runs'):
        os.mkdir('runs')
    input_tensor = torch.Tensor(12, 3, 32, 32).cuda()
    writer.add_graph(net, Variable(input_tensor, requires_grad=True))

    #create checkpoint folder to save model
    if not os.path.exists('checkpoint'):
        os.mkdir('checkpoint')
    checkpoint_path = os.path.join('checkpoint', 'rir-{epoch}.pt')

    best_acc = 0.0
    for epoch in range(1, 160):
        scheduler.step()
        train(epoch)
        acc = eval_training(epoch)

        #start to save best performance model after 130 epoch
        if epoch > 100 and best_acc < acc:
            torch.save(net.state_dict(), checkpoint_path.format(epoch=epoch))
            best_acc = acc
            continue

        if not epoch % 50:
            torch.save(net.state_dict(), checkpoint_path.format(epoch=epoch))

    writer.close()
        
 

    

if __name__ == '__main__':
    writer = SummaryWriter(log_dir=os.path.join('runs', datetime.now().isoformat()))
    main()
