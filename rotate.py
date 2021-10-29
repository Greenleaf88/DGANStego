import cv2
import numpy as np

imgPath = '/home/guoy/下载/2010_003222.jpg'
img = cv2.imread(imgPath)
cv2.imshow('test0',img)



w,h,depth = img.shape
img_change = cv2.getRotationMatrix2D((w/2,h/2),45,1)
res = cv2.warpAffine(img,img_change,(w,h))
cv2.imshow("test1",res)



crop_image = lambda img,x0,y0,w,h:img[x0:x0+2,y0:y0+h]

def rotate_image(img,angle,crop):


    w,h = img.shape[:2]

    angle %=360
    M_rotation = cv2.getRotationMatrix2D((w/2,h/2),angle,1)
    img_rotated = cv2.warpAffine(img,M_rotation,(w,h))

    if crop:
        angle_crop = angle % 180
        if angle > 90:
            angle_crop = 180 - angle_crop

        theta = angle_crop * np.pi / 180

        hw_ratio = float(h) / float(w)

        tan_theta = np.tan(theta)
        numerator = np.cos(theta) + np.sin(theta) *np.tan(theta)

        r = hw_ratio if h > w else 1 / hw_ratio

        denominator = numerator / denominator

        w_crop = int(crop_mult*w)
        h_crop = int(crop_mult*h)
        x0 = int((w -w_crop)/2)
        y0 = int((h - h_crop) / 2)

        img_rotated = crop_image(img_rotated,x0,y0,w_crop,h_crop)
        return img_rotated



    image_rotated = rotate_image(img,5,False)
    cv2.imshow("test2",image_rotated)