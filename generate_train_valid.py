import os
import glob


def generate_lfw():

    peopleDevTest = '/home/moliq/dataset/peopleDevTest.txt'
    peopleDevTrain = '/home/moliq/dataset/peopleDevTrain.txt'

    peopleDevTest_list = open(peopleDevTest, 'r').readlines()[1:]
    peopleDevTrain_list = open(peopleDevTrain, 'r').readlines()[1:]

    peopleDevTest_list = [i.strip().split('\t')[0] for i in peopleDevTest_list]
    peopleDevTrain_list = [i.strip().split('\t')[0]for i in peopleDevTrain_list]

    image_dir_path = '/home/moliq/dataset/lfw'
    train_images = []
    valid_images = []

    for folder in os.listdir(image_dir_path):
        if folder in peopleDevTrain_list:
            for i in os.listdir(os.path.join(image_dir_path, folder)):
                train_images.append(os.path.join(folder, i))
        elif folder in peopleDevTest_list:
            for i in os.listdir(os.path.join(image_dir_path, folder)):
                valid_images.append(os.path.join(folder, i))
        else:
            print('%s not in train or valid'%folder)

    print('train images: %d ; valid images: %d'%(len(train_images), len(valid_images)))

    with open('lfw_train.txt', 'w') as f:
        f.write('\n'.join(train_images))
    with open('lfw_valid.txt', 'w') as f:
        f.write('\n'.join(valid_images))

def generate_voc():

    trainval_txt = '/home/moliq/Documents/VOC2012/ImageSets/Main/trainval.txt'
    image_dir = '/home/moliq/Documents/VOC2012/JPEGImages'
    totoal_images = os.listdir(image_dir)

    with open(trainval_txt, 'r') as f:
        train_images = f.readlines()

    train_images = [i.strip()+'.jpg' for i in train_images]
    print 'train val txt have %d images'%len(train_images)
    train_images = [i for i in train_images if i in totoal_images]
    print '%d images are in JPEG folder'%(len(train_images))

    valid_images = [i for i in totoal_images if i not in train_images]
    print 'test images %d '%(len(valid_images))

    with open('voc_train.txt', 'w') as f:
        f.write('\n'.join(train_images))
    with open('voc_valid.txt', 'w') as f:
        f.write('\n'.join(valid_images))


if __name__ == '__main__':
    generate_voc()