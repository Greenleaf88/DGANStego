import torch
import torch.nn as nn
from torchvision import transforms
from loss import MS_SSIM
from pytorch_mssim import MSSSIM
from torch.autograd import Variable
from PIL import ImageChops
from dataset import DatasetFromFolder, getCoverExample, getSecretExample, DatasetFromFolder2
# from models.HidingUNet import UnetGenerator
# from models.RevealNet import RevealNet
# from model import HidingNet, RevealNet, UNet, Discriminator
from model import HidingNet, RevealNet, Discriminator
from XuNet import XuNet
from XuNet2 import XuNet2
import utils
from ssim import SSIM
from utils import to_np, plot_train_result, plot_result, plotCoverSecret, ssim_covers
from utils import plotCovers, plotSecrets
from PIL import Image
import argparse
import os, itertools
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time
from tqdm import tqdm
from math import log10
import random

def print_network(net):
    num_params = 0
    for param in net.parameters():
        num_params += param.numel()
    # print(net)
    print('Total number of parameters: {}'.format(num_params))

parser = argparse.ArgumentParser()
parser.add_argument('--batch_size', type=int, default=5, help='train batch size')
parser.add_argument('--lr', type=float, default=0.0001, help='learning rate')
parser.add_argument('--input_size', type=int, default=256, help='input size')
parser.add_argument('--resize_scale', type=int, default=256, help='resize scale (0 is false')
parser.add_argument('--crop_size', type=int, default=False, help='crop size (0 if false)')
parser.add_argument('--fliplr', type=bool, default=True, help='random fliplr True or False')
parser.add_argument('--num_epochs', type=int, default=120, help='num of epoch to train')
parser.add_argument('--decay_epoch', type=int, default=15, help='start decaying learning rate after this number')
parser.add_argument('--weight_decay', type=float, default=5e-3, help='weight decay')
parser.add_argument('--log_schedule', type=int, default=20, help='number of batch size to save snapshot after')
parser.add_argument('--lambdaA', type=float, default=0.5, help='lambadA for encoder')
parser.add_argument('--lambdaB', type=float, default=0.85, help='lambdaB for decoder')
parser.add_argument('--lambdaC', type=float, default=0.3, help='lambdaB for decoder')
parser.add_argument('--beta1', type=float, default=0.5, help='beta1 for Adam optimizer')
parser.add_argument('--beta2', type=float, default=0.999, help='beta2 for Adam optimizer')
parser.add_argument('--use_cuda', type=bool, default=True, help='use cuda or not')
parser.add_argument('--beginpoint', type=int, default=0, help='the begin epoch num')
params = parser.parse_args()
print(params)

data_dir = '/home/gy/Documents/JPEGImages/'
# # data_dir = '/home/jion/moliq/Documents/VOC2012/JPEGImages'
subfolder = 'voc_train.txt'
save_dir = './voc_results_2gan6/'
model_dir = './voc_checkpoint_2gan6/'
pics = '../pics_VOC'

#data_dir = '/home/gy/Documents/lfw'
#subfolder = 'lfw_train.txt'
#save_dir = './lfw_1_results/'
#model_dir = './lfw_1_checkpoint/'
#pics = '../pics_lfw'

if not os.path.exists(save_dir):
    os.mkdir(save_dir)
if not os.path.exists(model_dir):
    os.mkdir(model_dir)

# custom weights initialization called on netG and netD
def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        # m.weight.data.normal_(0.0, 0.02)
        nn.init.xavier_uniform(m.weight)
    elif classname.find('BatchNorm') != -1:
        # nn.init.xavier_uniform(m.weight)
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.fill_(0)
    # elif classname.find('InstanceNorm') != -1:
    #     m.weight.data.normal_(1.0, 0.02)
    #     m.bias.data.fill_(0)
    elif classname.find('ConvTranspose2d') != -1:
        nn.init.xavier_uniform(m.weight)
        m.bias.data.fill_(0)

# Models
# encoder = UnetGenerator(input_nc=2, output_nc=1, num_downs=7, output_function=nn.Sigmoid)
# decoder = RevealNet(nc=1)
encoder = HidingNet()
decoder = RevealNet(nc=1, nhf=32)
discriminator = XuNet(kernel_size=3, padding=1)
discriminator2 = XuNet2(kernel_size=3, padding=1)  # XuNet(kernel_size=3, padding=1)
print_network(encoder)
print_network(decoder)
print_network(discriminator)
# print_network(discriminator2)
if params.use_cuda:
    encoder.cuda()
    decoder.cuda()
    discriminator.cuda()
    discriminator2.cuda()
encoder.apply(weights_init)
decoder.apply(weights_init)

# loss function
BCE_loss = nn.BCELoss().cuda()
MSE_loss = nn.MSELoss().cuda()
SSIM_loss = SSIM(window_size=11).cuda()
MSSIM_loss = MSSSIM().cuda()


# Data pre-processing
transform = transforms.Compose([transforms.Scale(params.input_size),
                                transforms.ToTensor(),])
                                # transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225))])
                                # transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))])
# Train data
# train_data = DatasetFromFolder(data_dir, subfolder=subfolder, transform=transform, resize_scale=params.input_size,
#                                name=False)
train_data = DatasetFromFolder2(data_dir, subfolder=subfolder, transform=transform, resize_scale=params.resize_scale,
                                crop_size=params.crop_size, fliplr=params.fliplr)
train_data_loader = torch.utils.data.DataLoader(dataset=train_data,
                                                batch_size=params.batch_size,
                                                shuffle=True)

# Test data
# test_data = DatasetFromFolder(data_dir, subfolder='img_test', transform=transform, resize_scale=params.input_size,
#                               crop_size=params.crop_size, fliplr=params.fliplr, yuv=True)
# test_data = DatasetFromFolder2(data_dir, subfolder='lfw_test.txt', transform=transform,
test_data = DatasetFromFolder2('/home/gy/Documents/JPEGImages/', subfolder='voc_valid.txt', transform=transform,
                               resize_scale=params.input_size)
test_data_loader = torch.utils.data.DataLoader(dataset=test_data,
                                               batch_size=1,
                                               shuffle=False)

# image pool
num_pool = 50
# cover_pool = utils.ImagePool(num_pool)
stego_pool = utils.ImagePool(num_pool)
secret_pool = utils.ImagePool(num_pool)

# optimizers
encoder_optimizer = torch.optim.Adam(encoder.parameters(), lr=params.lr,
                                     betas=(params.beta1, params.beta2), weight_decay=params.weight_decay)
decoder_optimizer = torch.optim.Adam(decoder.parameters(), lr=params.lr,
                                     betas=(params.beta1, params.beta2), weight_decay=params.weight_decay)
# encoder_optimizer = torch.optim.SGD(encoder.parameters(), lr=params.lr, weight_decay=1e-8)
# decoder_optimizer = torch.optim.SGD(decoder.parameters(), lr=params.lr, weight_decay=1e-8)
discriminator_optimizer = torch.optim.SGD(discriminator.parameters(), lr=params.lr/3, weight_decay=1e-8)
discriminator2_optimizer = torch.optim.SGD(discriminator2.parameters(), lr=params.lr/3, weight_decay=1e-8)

# Training the model
# encoder_losses = list()
# decoder_losses = list()
avg_loss = list()
encoder_ssim = list()
decoder_ssim = list()
min_en_loss = min_de_loss = min_loss = 10000
fig1, ax1 = plt.subplots()
# fig2, ax2 = plt.subplots()
# fig3, ax3 = plt.subplots()
fig4, ax4 = plt.subplots()

def train(epoch):
    global avg_loss
    global encoder_losses, decoder_losses
    encoder.train()
    decoder.train()
    if epoch >= params.decay_epoch and epoch % 3 == 0:
        encoder_optimizer.param_groups[0]['lr'] *= 0.9
        decoder_optimizer.param_groups[0]['lr'] *= 0.9
        encoder_optimizer.param_groups[0]['weight_decay'] *= 0.95
        decoder_optimizer.param_groups[0]['weight_decay'] *= 0.95
    print('current learning rate: {:.6f} weight decay: {:.6f}'.format(
        encoder_optimizer.param_groups[0]['lr'], encoder_optimizer.param_groups[0]['weight_decay']))

    # show3(epoch)

    # training
    for idx, (secret, cover, target) in enumerate(train_data_loader, 1):
        transform1 = transforms.Compose([
            transforms.ToTensor(),
        ]
        )

        # def ImgOfffSet(Img, xoff, yoff):
        #     width, height = Img.size
        #     c = ImageChops.offset(Img, xoff, yoff)
        #     c.paste((0, 0, 0), (0, 0, xoff, height))
        #     c.paste((0, 0, 0), (0, 0, width, yoff))
        #     return c
        # input image data
        if params.use_cuda:
            secret = secret.cuda()
            cover = cover.cuda()
            target = target.cuda()
        secret = Variable(secret)
        cover = Variable(cover)
        target = Variable(target)
        # print secret.shape
        stego = encoder(secret, cover)
        # 这里对stego添加加噪生成stego2用于训练GAN2
        # print(stego.shape)
        # stego2=torch.Tensor(stego.shape[0],3,256,256).copy_(stego)
        # print  (stego2.shape)
        stego3=torch.Tensor(stego.shape[0],3,260,260)
        stego2 = stego.cpu().detach()
        # stego3 =
        # print  (stego3.shape)
        # print  (stego3[0].shape)
        # stego2 = stego.rotate(5)
        # stego2 = stego.cpu().detach().numpy()
        #print(stego.shape)
        for i in range(stego.shape[0]):
            img = transforms.ToPILImage()(stego2[i]).convert('RGB')
            # print (img.size)
            # (x, y) = img.size
            # x_s = 128
            # y_s = y * x_s // x
            # img3 = img.point(lambda i: i * 2)
            img3 = img.resize((260, 260), Image.ANTIALIAS)
            # print (img3.shape)
            # stego2=Image.fromarray(stego2)
            # img2 = img.rotate(random.randint(1,5))
            # img3 = ImgOfffSet(img,random.randint(0,10),0)



            # img3 = img.transpose(img.FLIP_LEFT_RIGHT)
            # img4 = img.transpose(img.FLIP_TOP_BOTTOM)
            # stego2[0] = transform1(img2)
            stego3[i] = transform1(img3)

        secret2 = secret.cpu().detach()
        secret_half = torch.Tensor(secret.shape[0],1,260,260)
        for i in range(secret.shape[0]):
            img = transforms.ToPILImage()(secret2[i]).convert('L')
            img3 = img.resize((260, 260), Image.ANTIALIAS)
            secret_half[i] = transform1(img3)

        # stego4[0] = transform1(img4)
        # stego5[0] = transform1(img5)
        #print(stego2.shape)
        # stego2=stego2.cuda()
        stego3=stego3.cuda()
        secret_half=secret_half.cuda()
        # stego4=stego4.cuda()
        # stego5 = stego5.cuda()
        # secret2 = decoder(stego+stego3)
        secret2 = decoder(stego3)
        cls1 = discriminator(stego3)
        cls2 = discriminator2(secret2)

        disloss1 = BCE_loss(cls1, Variable(torch.ones(cls1.size()).cuda() * random.uniform(0.8, 1.2)))
        disloss2 = BCE_loss(cls2, Variable(torch.ones(cls2.size()).cuda() * random.uniform(0.8, 1.2)))
        disloss_total=(disloss1+disloss2)*0.5

        encoder_mse = MSE_loss(stego, target)
        decoder_mse = MSE_loss(secret2, secret_half)
        
        encoder_ssim = SSIM_loss(stego, target)
        decoder_ssim = SSIM_loss(secret2, secret_half)
        if epoch == 1 and idx <= 20:
            encoder_mssim = SSIM_loss(stego, target)
            decoder_mssim = SSIM_loss(secret2, secret_half)
        else:
            stego = Variable(stego)
            secret2 = Variable(secret2)
            encoder_mssim = MSSIM_loss(stego, target)
            decoder_mssim = MSSIM_loss(secret2, secret_half)
        encoder_loss = params.lambdaA * (1 - encoder_mssim) + (1 - params.lambdaA) * (1 - encoder_ssim) \
                       + params.lambdaC * encoder_mse
        decoder_loss = params.lambdaA * (1 - decoder_mssim) + (1 - params.lambdaA) * (1 - decoder_ssim) \
                       + params.lambdaC * decoder_mse
        loss = encoder_loss + params.lambdaB * decoder_loss + disloss1
        # loss = encoder_loss + params.lambdaB * decoder_loss + disloss1
        # loss = (encoder_loss + params.lambdaA * ssim1) + params.lambdaB * (decoder_loss + params.lambdaA * ssim2)
        avg_loss.append(loss.item())
        avg_loss.append(loss.item())
        encoder_optimizer.zero_grad()
        decoder_optimizer.zero_grad()
        loss.backward()
        encoder_optimizer.step()
        decoder_optimizer.step()

        if idx % params.log_schedule == 0:
                print('Epoch [{}/{}]  Step [{}/{}]  Loss {:.4f} encoder_ssim {:.4f} enocder_mssim {:.4f} encoder_mse {:.4f}'
                  '  decoder_ssim {:.4f} decoder_mssim {:.4f} decoder_mse {:.4f} disloss {:.4f}'.format(
                epoch, params.num_epochs, idx*params.batch_size, len(train_data_loader.dataset), loss.item(),
                # encoder_mssim.item(), encoder_mse.item(), decoder_mssim.item(), decoder_mse.item()))
                encoder_ssim.item(), encoder_mssim.item(), encoder_mse.item(),
                decoder_ssim.item(), decoder_mssim.item(), decoder_mse.item(), disloss1.item()))
            # mssim
            # print('Epoch [{}/{}]  Step [{}/{}]  Loss {:.4f} en_ssim {:.4f} en_mssim {:.4f} de_ssim {:.4f} de_mssim {:.4f}'.format(
            #     epoch, params.num_epochs, idx*params.batch_size, len(train_data_loader.dataset), loss.item(),
            #     encoder_ssim.item(), encoder_mssim.item(), decoder_ssim.item(), decoder_mssim.item()))
            # print('Epoch [{}/{}] step [{}/{}] loss {:.4f} en_mse {:.4f} en_sim {:.4f} de_mse {:.4f} de_sim {:.4f}'.format(
            #     epoch, params.num_epochs, idx*params.batch_size, len(train_data_loader.dataset), loss.item(),
            #     encoder_loss.item(), encoder_ssim.item(), decoder_loss.item(), decoder_ssim.item()))
            # show3(epoch)
        if idx % (params.log_schedule * 5) == 0:
            ax1.plot(avg_loss, 'r')
            fig1.savefig(save_dir + 'loss.jpg')

        # train discriminator
        if idx % 5 == 0:
            cls_cover = discriminator(target)
            stego = stego_pool.query(stego)
            cls_stego = discriminator(stego)
            discover = BCE_loss(cls_cover, Variable(torch.ones(cls_cover.size()).cuda() * random.uniform(0.8, 1.2)))
            disstego = BCE_loss(cls_stego, Variable(torch.zeros(cls_stego.size()).cuda() * random.uniform(0., 0.2)))
            disloss_1= discover + disstego
            cls_secret = discriminator2(secret)
            secret2=secret_pool.query(secret2)
            cls_secret2 = discriminator2(secret2)

            dissecret = BCE_loss(cls_secret, Variable(torch.ones(cls_secret.size()).cuda() * random.uniform(0.8, 1.2)))
            dissecret2 = BCE_loss(cls_secret2, Variable(torch.zeros(cls_secret2.size()).cuda() * random.uniform(0., 0.2)))
            disloss_2 = dissecret + dissecret2 #+disloss1

            disloss=disloss_1+disloss_2
            #print(stego)
            discriminator.zero_grad()
            discriminator2.zero_grad()
            disloss_1.backward()
            # rint(secret2)
            disloss_2.backward()
            discriminator_optimizer.step()
            discriminator2_optimizer.step()


    show3(epoch)

    torch.save(encoder.state_dict(), model_dir + 'encoder_{}.pkl'.format(epoch))
    torch.save(decoder.state_dict(), model_dir + 'decoder_{}.pkl'.format(epoch))
    torch.save(discriminator.state_dict(), model_dir + 'discriminator_{}.pkl'.format(epoch))
    torch.save(discriminator2.state_dict(), model_dir + 'discriminator2_{}.pkl'.format(epoch))

def val(epoch=None):
    if epoch:
        encoder.load_state_dict(torch.load(model_dir + 'encoder_{:d}.pkl'.format(epoch)))
        decoder.load_state_dict(torch.load(model_dir + 'decoder_{:d}.pkl'.format(epoch)))
    en_loss, de_loss = list(), list()
    encoder.eval()
    decoder.eval()
    for idx, (secret, cover) in enumerate(test_data_loader):
        concat = torch.cat([secret, cover], dim=1)
        if params.use_cuda:
            secret = secret.cuda()
            cover = cover.cuda()
            concat = concat.cuda()
        secret = Variable(secret)
        cover = Variable(cover)
        concat = Variable(concat)
        stego = encoder(concat)
        secret2 = decoder(stego)

        loss1 = SSIM_loss(stego, cover)
        loss2 = SSIM_loss(secret2, secret)
        en_loss.append(loss1.item())
        de_loss.append(loss2.item())
        if idx % params.log_schedule == 0:
            print('{} en_loss {:.4f} de_loss {:.4f}'.format(idx, loss1.item(), loss2.item()))
    if epoch:
        print('Epoch {} en_loss {:.4f} de_loss {:.4f}'.format(epoch, sum(en_loss)/len(en_loss), sum(de_loss)/len(de_loss)))
    else:
        print('This epoch en_loss {:.4f} de_loss {:.4f}'.format(sum(en_loss)/len(en_loss), sum(de_loss)/len(de_loss)))

def val2(epoch=None, mode='eval', ifprint=False):
    if epoch:
        encoder.load_state_dict(torch.load(model_dir + 'encoder_{:d}.pkl'.format(epoch)))
        decoder.load_state_dict(torch.load(model_dir + 'decoder_{:d}.pkl'.format(epoch)))
    en_sim, de_sim = list(), list()
    en_psnr, de_psnr = list(), list()
    if mode == 'eval':
        encoder.eval()
        decoder.eval()
    else:
        encoder.train()
        decoder.train()
    for idx, (secret, cover, target) in enumerate(test_data_loader):
        if params.use_cuda:
            secret = secret.cuda()
            cover = cover.cuda()
            target = target.cuda()
        secret = Variable(secret)
        cover = Variable(cover)
        target = Variable(target)
        stego = encoder(secret, cover)
        secret2 = decoder(stego)

        sim1 = SSIM_loss(stego, target)
        mse1 = MSE_loss(stego, target)
        psnr1 = 10 * log10(1 / mse1.item())
        sim2 = SSIM_loss(secret2, secret)
        mse2 = MSE_loss(secret2, secret)
        psnr2 = 10 * log10(1 / mse2.item())
        en_sim.append(sim1.item())
        de_sim.append(sim2.item())
        en_psnr.append(psnr1)
        de_psnr.append(psnr2)
        if ifprint:
            if idx % params.log_schedule == 0:
                print('{} en_sim {:.4f} de_sim {:.4f} en_psnr {:.4f} de_psnr {:4f}'.format(
                    idx, sim1.item(), sim2.item(), psnr1, psnr2))
    # print(mode)
    if epoch:
        print('Epoch {} en_sim {:.4f} de_sim {:.4f} en_psnr {:.4f} de_psnr {:.4f}'.format(
            epoch, sum(en_sim)/len(en_sim), sum(de_sim)/len(de_sim), sum(en_psnr)/len(en_psnr), sum(de_psnr)/len(de_psnr)))
    else:
        print('This epoch en_sim {:.4f} de_sim {:.4f} en_psnr {:.4f} de_psnr {:.4f}'.format(
            sum(en_sim)/len(en_sim), sum(de_sim)/len(de_sim), sum(en_psnr)/len(en_psnr), sum(de_psnr)/len(de_psnr)))

def show(epoch):
    stegoExample = encoder(secretExample, coverExample)
    secretRevealed = decoder(stegoExample)
    plotCovers(coverExample, stegoExample, imgs, epoch, save_dir=save_dir)
    plotSecrets(secretExample, secretRevealed, epoch, save_dir=save_dir)

def show2(epoch):
    encoder.load_state_dict(torch.load(model_dir + 'encoder_{:d}.pkl'.format(epoch)))
    decoder.load_state_dict(torch.load(model_dir + 'decoder_{:d}.pkl'.format(epoch)))
    encoder.train()
    decoder.train()
    cover, yuv = getCoverExample('../pics_VOC/1.JPEG', params.input_size)
    secret = getSecretExample('../pics_VOC/4.JPEG', params.input_size)
    cover = transform(cover)
    secret = transform(secret)
    cover.resize_(1, 1, params.input_size, params.input_size)
    secret.resize_(1, 1, params.input_size, params.input_size)
    concat = torch.cat([secret, cover], dim=1)
    if params.use_cuda:
        concat = concat.cuda()
    
    concat = Variable(concat)
    stego = encoder(concat)
    stego = to_np(stego)
    stego = (((stego - stego.min()) * 255) / (stego.max() - stego.min())).astype(np.uint8)
    print(np.shape(stego))
    stego = stego[0][0]
    stego = Image.fromarray(stego, 'L')
    stego.show()
    yuv[:, :, 0] = stego
    img = Image.fromarray(yuv, 'YCbCr')
    stego = img.convert('RGB')

    stego.save('./lfw_mssim_results/stego.bmp')
    stego, _  = getCoverExample('./lfw_mssim_results/stego.bmp', params.input_size)
    
    stego = transform(stego)
    stego.resize_(1, 1, params.input_size, params.input_size)
    stego = stego.cuda()
    stego = Variable(stego)
    secret2 = decoder(stego)
    secret2 = to_np(secret2)
    secret2 = (((secret2 - secret2.min()) * 255) / (secret2.max() - secret2.min())).astype(np.uint8)
    secret2 = secret2[0][0]
    secret2 = Image.fromarray(secret2, 'L')
    secret2.show()
    secret2.save('./lfw_mssim_results/secret.png')



def show3(epoch):
    # Get specific test images
    coverExample_1, img1 = getCoverExample(os.path.join(pics, '1.JPEG'), params.input_size)
    coverExample_2, img2 = getCoverExample(os.path.join(pics, '2.JPEG'), params.input_size)
    coverExample_3, img3 = getCoverExample(os.path.join(pics, '3.JPEG'), params.input_size)
    # coverExample_4, img4 = getCoverExample(os.path.join(pics, '4.JPEG'), params.input_size)
    # imgs = [img1, img2, img3, img4]
    imgs = [img1, img2, img3]

    secretExample_1 = getSecretExample(os.path.join(pics, '4.JPEG'), params.input_size)
    secretExample_2 = getSecretExample(os.path.join(pics, '5.JPEG'), params.input_size)
    secretExample_3 = getSecretExample(os.path.join(pics, '6.JPEG'), params.input_size)
    # secretExample_4 = getSecretExample(os.path.join(pics, '7.JPEG'), params.input_size)

    coverExample_1 = transform(coverExample_1)
    coverExample_2 = transform(coverExample_2)
    coverExample_3 = transform(coverExample_3)
    # coverExample_4 = transform(coverExample_4)
    secretExample_1 = transform(secretExample_1)
    secretExample_2 = transform(secretExample_2)
    secretExample_3 = transform(secretExample_3)
    # secretExample_4 = transform(secretExample_4)

    coverExample_1.resize_(1, 3, params.input_size, params.input_size)
    coverExample_2.resize_(1, 3, params.input_size, params.input_size)
    coverExample_3.resize_(1, 3, params.input_size, params.input_size)
    # coverExample_4.resize_(1, 3, params.input_size, params.input_size)
    secretExample_1.resize_(1, 1, params.input_size, params.input_size)
    secretExample_2.resize_(1, 1, params.input_size, params.input_size)
    secretExample_3.resize_(1, 1, params.input_size, params.input_size)
    # secretExample_4.resize_(1, 1, params.input_size, params.input_size)

    
    # coverExample = torch.cat([coverExample_1, coverExample_2, coverExample_3, coverExample_4], dim=0)
    coverExample = torch.cat([coverExample_1, coverExample_2, coverExample_3], dim=0)
    # secretExample = torch.cat([secretExample_1, secretExample_2, secretExample_3, secretExample_4], dim=0)
    secretExample = torch.cat([secretExample_1, secretExample_2, secretExample_3], dim=0)
    coverExample = Variable(coverExample.cuda())
    secretExample = Variable(secretExample.cuda())
    # concate = Variable(concate.cuda())
    stegoExample = encoder(secretExample, coverExample)
    secretRevealed = decoder(stegoExample)
    plotCoverSecret(imgs, stegoExample, secretExample, secretRevealed, epoch, save_dir=save_dir)

def total_train(beginpoint=0):
    start = time.time()
    if beginpoint > 0:
        encoder.load_state_dict(torch.load(model_dir + 'encoder_{}.pkl'.format(beginpoint)))
        decoder.load_state_dict(torch.load(model_dir + 'decoder_{}.pkl'.format(beginpoint)))
        discriminator.load_state_dict(torch.load(model_dir + 'discriminator_{}.pkl'.format(beginpoint)))
        discriminator2.load_state_dict(torch.load(model_dir + 'discriminator2_{}.pkl'.format(beginpoint)))
    print("Starting to train the model...")
    for epoch in range(1+beginpoint, params.num_epochs + 1):
        train(epoch)
        val2(mode='train')
        thistime = time.time()
        print("The model has been training for {:.2f} seconds".format(thistime - start))

def get_stegos(epoch, input_dir, stego_dir=None, thres=0.0):
    if not stego_dir:
        stego_dir = os.path.join(os.path.dirname('/home/gy/Documents/'), 'voc5_resize_1.2_1')
    train_data = DatasetFromFolder2(input_dir, subfolder='test1.txt', transform=transform,
                                    resize_scale=params.resize_scale,
                                    crop_size=params.crop_size, fliplr=params.fliplr, name=True)
    train_data_loader = torch.utils.data.DataLoader(dataset=train_data,
                                                    batch_size=1,  # params.batch_size,
                                                    shuffle=True)
    start = time.time()
    encoder.load_state_dict(torch.load('voc_checkpoint_1gan/' + 'encoder_{}.pkl'.format(epoch)))
    encoder.train()

    decoder.load_state_dict(torch.load('voc_checkpoint_1gan/' + 'decoder_{}.pkl'.format(epoch)))
    decoder.train()

    similarity = list()
    if not os.path.exists(stego_dir):
        os.mkdir(stego_dir)
    for idx, (secret, cover, target, fns) in enumerate(train_data_loader, 1):
        # print idx
        # print fns
        transform1 = transforms.Compose([
            transforms.ToTensor(),
        ]
        )
        secret2 = secret.cpu().detach()
        secret_re = torch.Tensor(secret.shape[0], 1, 307, 307)
        for i in range(secret.shape[0]):
            img = transforms.ToPILImage()(secret2[i]).convert('L')
            img3 = img.resize((307, 307), Image.ANTIALIAS)
            secret_re[i] = transform1(img3)
        secret_re = secret_re.cuda()
        cover2 = cover.cpu().detach()
        cover_re = torch.Tensor(cover.shape[0], 3, 307, 307)
        for i in range(cover.shape[0]):
            img = transforms.ToPILImage()(cover2[i]).convert('RGB')
            img3 = img.resize((307, 307), Image.ANTIALIAS)
            cover_re[i] = transform1(img3)
        cover_re = cover_re.cuda()
        # secret = secret.cuda()
        # cover = cover.cuda()
        # target = target.cuda()
        secret_re = Variable(secret_re)
        cover_re = Variable(cover_re)
        stego = encoder(secret_re, cover_re)
        # stego = encoder(secret, cover)
        # stego2=torch.Tensor(1,3,256,256).copy_(stego)
        # # stego2 = stego.rotate(5)
        # # stego2 = stego.cpu().detach().numpy()
        # #print(stego.shape)
        # img = transforms.ToPILImage()(stego2[0]).convert('RGB')
        # # stego2=Image.fromarray(stego2)
        # # img=img.rotate(2)
        # img = ImgOfffSet(img,0,5)
        # stego2[0] = transform1(img)
        #print(stego2.shape)
        # stego2=stego2.cuda()
        secret2 = decoder(stego)
        # # secret3 = secret.cpu().detach().numpy()
        # #print(secret2.shape)
        # secret3 = torch.Tensor(1, 1, 256, 256).copy_(secret)
        # img = transforms.ToPILImage()(secret3[0]).convert('L')
        # img = img.convert('RGB')
        # img = ImgOfffSet(img, 0, 5)
        # img = img.convert('L')
        # # secret3=Image.fromarray(secret3)
        #
        # secret3[0] = transform1(img)
        # secret3=secret3.cuda()

        # sim3 = SSIM_loss(stego, target).item()
        sim3 = SSIM_loss(secret2, secret_re).item()
        if sim3 > thres:
            similarity.append(sim3)
            utils.saveStegos([stego, secret2], fns, save_dir=stego_dir)
        if idx % params.log_schedule == 0:
            print('{}/{}'.format(idx*params.batch_size, len(train_data_loader.dataset)))
            print(sim3, fns)
    print(sum(similarity) / len(similarity))
    print(len([sim for sim in similarity if sim >= 0.95]))
    print('Time consumption: {:.2f} sec'.format(time.time() - start))

def get_performance(name, dataLoader):
    ssim_encoder = []
    ssim_decoder = []
    mse_encoder = []
    mse_decoder = []
    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()

    for epoch in range(1, 51):
        encoder.load_state_dict(torch.load('./checkpoint/encoder_{:d}.pkl'.format(epoch)))
        decoder.load_state_dict(torch.load('./checkpoint/decoder_{:d}.pkl'.format(epoch)))
        encoder.eval()
        decoder.eval()
        mse1, mse2, ssim1, ssim2, num = list(), list(), list(), list(), 0
        for idx, (secret, cover) in tqdm(enumerate(dataLoader)):
            num += 1
            if params.use_cuda:
                secret = secret.cuda()
                cover = cover.cuda()
            secret = Variable(secret)
            cover = Variable(cover)
            stego = encoder(secret, cover)
            secret2 = decoder(stego)
            mse1.append(MSE_loss(stego, cover).item())
            mse2.append(MSE_loss(secret2, secret).item())
            ssim1.append(SSIM_loss(stego, cover).item())
            ssim2.append(SSIM_loss(secret2, secret).item())
        tmp1, tmp2, tmp3, tmp4 = sum(ssim1)/num, sum(ssim2)/num, sum(mse1)/num, sum(mse2)/num
        print('training Epoch {:d}/50, ssim_encoder: {:5f}, ssim_decoder: {:5f}, mse_encoder: {:5f}, mse_decoder: {:5}'.format(
            epoch, tmp1, tmp2, tmp3, tmp4))
        ssim_encoder.append(tmp1)
        ssim_decoder.append(tmp2)
        np.save('./results/{:s}_ssim_encoder.npy'.format(name), np.array(ssim_encoder))
        np.save('./results/{:s}_ssim_decoder.npy'.format(name), np.array(ssim_decoder))
        mse_encoder.append(tmp3)
        mse_decoder.append(tmp4)
        np.save('./results/{:s}_mse_encoder.npy'.format(name), np.array(mse_encoder))
        np.save('./results/{:s}_mse_decoder.npy'.format(name), np.array(mse_decoder))
        ax1.plot(ssim_encoder, 'r')
        ax1.plot(ssim_decoder, 'b')
        fig1.savefig('{:s}_ssim.jpg'.format(name))
        ax2.plot(mse_encoder, 'r')
        ax2.plot(mse_decoder, 'b')
        fig2.savefig('{:s}_mse.jpg'.format(name))

def get_performance2():
    ssim_encoder = [[], []]
    ssim_decoder = [[], []]
    mse_encoder = [[], []]
    mse_decoder = [[], []]
    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()
    fig3, ax3 = plt.subplots()
    fig4, ax4 = plt.subplots()

    for epoch in range(1, 51):
        encoder.load_state_dict(torch.load('./checkpoint/encoder_{:d}.pkl'.format(epoch)))
        decoder.load_state_dict(torch.load('./checkpoint/decoder_{:d}.pkl'.format(epoch)))
        encoder.eval()
        decoder.eval()
        mse1, mse2, ssim1, ssim2, num = list(), list(), list(), list(), 0
        for idx, (secret, cover) in tqdm(enumerate(train_data_loader)):
            num += 1
            if params.use_cuda:
                secret = secret.cuda()
                cover = cover.cuda()
            secret = Variable(secret)
            cover = Variable(cover)
            stego = encoder(secret, cover)
            secret2 = decoder(stego)
            mse1.append(MSE_loss(stego, cover).item())
            mse2.append(MSE_loss(secret2, secret).item())
            ssim1.append(SSIM_loss(stego, cover).item())
            ssim2.append(SSIM_loss(secret2, secret).item())
        tmp1, tmp2, tmp3, tmp4 = sum(ssim1)/num, sum(ssim2)/num, sum(mse1)/num, sum(mse2)/num
        print('training Epoch {:d}/50, ssim_encoder: {:5f}, ssim_decoder: {:5f}, mse_encoder: {:5f}, mse_decoder: {:5}'.format(
            epoch, tmp1, tmp2, tmp3, tmp4))
        ssim_encoder[0].append(tmp1)
        ssim_decoder[0].append(tmp2)
        mse_encoder[0].append(tmp3)
        mse_decoder[0].append(tmp4)
        ax1.plot(ssim_encoder[0], 'r')
        ax1.plot(ssim_decoder[0], 'b')
        fig1.savefig('{:s}_ssim.jpg'.format('train'))
        ax2.plot(mse_encoder[0], 'r')
        ax2.plot(mse_decoder[0], 'b')
        fig2.savefig('{:s}_mse.jpg'.format('train'))

    for epoch in range(1, 51):
        encoder.load_state_dict(torch.load('./checkpoint/encoder_{:d}.pkl'.format(epoch)))
        decoder.load_state_dict(torch.load('./checkpoint/decoder_{:d}.pkl'.format(epoch)))
        encoder.eval()
        decoder.eval()
        mse1, mse2, ssim1, ssim2, num = list(), list(), list(), list(), 0
        for idx, (secret, cover) in tqdm(enumerate(test_data_loader)):
            num += 1
            if params.use_cuda:
                secret = secret.cuda()
                cover = cover.cuda()
            secret = Variable(secret)
            cover = Variable(cover)
            stego = encoder(secret, cover)
            secret2 = decoder(stego)
            mse1.append(MSE_loss(stego, cover).item())
            mse2.append(MSE_loss(secret2, secret).item())
            ssim1.append(SSIM_loss(stego, cover).item())
            ssim2.append(SSIM_loss(secret2, secret).item())

        tmp1, tmp2, tmp3, tmp4 = sum(ssim1) / num, sum(ssim2) / num, sum(mse1) / num, sum(mse2) / num
        print(
        'Validating Epoch {:d}/50, ssim_encoder: {:5f}, ssim_decoder: {:5f}, mse_encoder: {:5f}, mse_decoder: {:5}'.format(
            epoch, tmp1, tmp2, tmp3, tmp4))
        ssim_encoder[1].append(tmp1)
        ssim_decoder[1].append(tmp2)
        mse_encoder[1].append(tmp3)
        mse_decoder[1].append(tmp4)
        plot_result('ssim', ssim_encoder+ssim_decoder)
        plot_result('mse', mse_decoder+mse_decoder)
        ax3.plot(ssim_encoder[1], 'r')
        ax3.plot(ssim_decoder[1], 'b')
        fig3.savefig('{:s}_ssim.jpg'.format('val'))
        ax4.plot(mse_encoder[1], 'r')
        ax4.plot(mse_decoder[1], 'b')
        fig4.savefig('{:s}_mse.jpg'.format('val'))


if __name__ == '__main__':
    start = time.time()
    #total_train(beginpoint=0)
    # val2(epoch=80, mode='train')
    get_stegos(epoch=80, input_dir=data_dir)
    print('Time consumption: {:.2f} secs'.format(time.time() - start))
    