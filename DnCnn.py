import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader
import cv2
import numpy as np
import glob
import os
import re
import matplotlib.pyplot as plt
#def getnoise(noise_level = 25):


patch_size, stride = 40, 10
aug_number = 1
batch_size = 128
num_epoch = 50
modelpath = './modeldata'

if not os.path.exists(modelpath):
    os.mkdir(modelpath)


def data_aug(img):

    num = np.random.randint(0,8)
    if num == 0:
        return img
    elif num ==1:
        return np.flipud(img)
    elif num ==2:
        return np.rot90(img)
    elif num ==3:
        return np.flipud(np.rot90(img))
    elif num ==4:
        return np.rot90(img,k=2)
    elif num ==5:
        return np.flipud(np.rot90(img,k=2))
    elif num ==6:
        return np.rot90(img,k=3)
    elif num ==7:
        return np.flipud(np.rot90(img,k=3))


def makepatches(file_name):
    img = cv2.imread(file_name,cv2.IMREAD_GRAYSCALE) #grayscale
    patches = []
    img_size = img.shape

    for i in range(0,img_size[0]-patch_size+1,stride):
        for j in range(0,img_size[1]-patch_size+1,stride):
            cropped_img = img[i:i+patch_size,j:j+patch_size]
            for k in range(aug_number):
                cropped_img = data_aug(cropped_img)
                patches.append(cropped_img)

    return patches

def trainimage_generator(dirpath):
    filenames = glob.glob(dirpath+"/*.png")

    dataset = []

    for filename in filenames:
        patchset = makepatches(filename)
        for patch in patchset:
            dataset.append(patch)

    data = np.array(dataset,dtype = 'uint8')
    data = np.expand_dims(data, axis=3)
    delete_range = len(data)-(len(data)//batch_size)*batch_size
    #print(delete_range)
    train_dataset = np.delete(data, range(delete_range), axis = 0)
    return train_dataset

class Dataset_Denoising():
    def __init__(self,xs,sigma):
        self.xs = xs
        self.sigma = sigma

    def __getitem__(self, index):
        batch_x = self.xs[index]
        noise = torch.randn(batch_x.size()).mul_(self.sigma/255.0)
        batch_y = batch_x +noise
        return batch_y, batch_x

    def __len__(self):
        return self.xs.size(0)



class DnCNN(nn.Module):
    def __init__(self,iscolor = 'False'):
        super(DnCNN, self).__init__()
        #def type 1(first) layer
        if(iscolor == 'False'):
            color_channel = 1
        else:
            color_channel = 3
        self.type1_conv = nn.Conv2d(in_channels=color_channel,out_channels=64,kernel_size=3,padding='same', padding_mode='zeros',bias='True')

        #def type2 layer
        self.type2_conv = nn.Conv2d(in_channels=64, out_channels=64, kernel_size=3, padding='same', padding_mode= 'zeros',bias='True')
        self.type2_bn = nn.BatchNorm2d(64,eps = 0.0001, momentum = 0.95)

        #def type3 layer
        self.type3_conv = nn.Conv2d(in_channels=64,out_channels=color_channel, kernel_size=3 ,padding='same', padding_mode='zeros',bias='True')

    def make_model(self,depth):
        modules = []
        modules.append(self.type1_conv)
        modules.append(F.relu)
        for i in range(depth-2):
            modules.append(self.type2_conv)
            modules.append(self.type2_bn)
            modules.append(F.relu())
        modules.append(self.type3_conv)

        model = nn.Sequential(*modules)
        return model

    def forward(self, x, depth):
        model = self.make_model(depth)
        out = model(x)
        return out

def findLastepoch(dirpath):
    filelist = glob.glob(os.path.join(dirpath,"model_*.pth"))
    if filelist:
        epochlist = []
        for file_ in filelist:
            pre_epoch = re.findall('\d+',file_)
            epochlist.append(int(pre_epoch[0]))
    else:
        return 0

    return max(epochlist)

if __name__ == '__main__':
    #create training dataset


    #create model
    Dncnn = DnCNN(iscolor='false')
    start_epoch = findLastepoch(modelpath)
    if start_epoch>0:
        print("start from epoch %03d" % start_epoch)
        Dncnn = torch.load(os.path.join(modelpath,'model_%03d.pth' % start_epoch))

    Dncnn.train()

    optimizer = optim.Adam(Dncnn.parameters(), lr = 0.01)
    criterion = nn.MSELoss(reduction='sum')
    #loss = criterion()
    scheduler = optim.lr_scheduler.MultiStepLR(optimizer, milestones=[30,60,90], gamma = 0.2)

    for epoch in range(start_epoch, num_epoch):
        scheduler.step(epoch)
        trainset = trainimage_generator('./data/Train400')
        #print(trainset.shape)
        trainset = trainset.astype('float32')/255.0
        trainset = torch.from_numpy(trainset.transpose(0,3,1,2))
        print(trainset.shape)
        train_dataset = Dataset_Denoising(trainset, sigma=25)
        DLoader = DataLoader(dataset=train_dataset, batch_size=batch_size, drop_last=True, )

        epochloss = 0

        for batch_num, batch in enumerate(DLoader):
            batch_x = batch[1]
            batch_y = batch[0]
            optimizer.zero_grad()
            loss = criterion(Dncnn(batch_y), batch_x)
            epochloss += loss.item()/2
            loss.backward()
            optimizer.step()
            print(batch_num)
            if batch_num % 10 ==0:
                print('%4d %4d/%4d loss = %2.4f' %(epoch+1, trainset.size(0), loss.item()/batch_size))

        torch.save(Dncnn,os.path.join(modelpath,'model_%03d.pth'%(epoch+1)))







#plt.imshow(np.reshape(trainset[400],(40,40)))
#plt.show()
#
