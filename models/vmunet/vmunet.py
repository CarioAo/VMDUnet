from .vmamba import VSSM
import torch
from torch import nn
from models.vmunet.utils.dca import DCA


class VMUNet(nn.Module):
    def __init__(self, 
                 input_channels=3, 
                 num_classes=1,
                 depths=[2, 2, 9, 2], 
                 depths_decoder=[2, 9, 2, 2],
                 drop_path_rate=0.2,
                 load_ckpt_path=None,
                ):
        super().__init__()

        self.load_ckpt_path = load_ckpt_path
        self.num_classes = num_classes

        self.vmunet = VSSM(in_chans=input_channels,
                           num_classes=num_classes,
                           depths=depths,
                           depths_decoder=depths_decoder,
                           drop_path_rate=drop_path_rate,
                        )

        self.DCA = DCA(n=1,
                       features=[96, 192, 384, 768],
                       strides=[8, 8 // 2, 8 // 4, 8 // 8],
                       patch=16,
                       spatial_att=True,
                       channel_att=True,
                       spatial_head=[4, 4, 4, 4],
                       channel_head=[1, 1, 1, 1],
                       )
    
    def forward(self, x):
        if x.size()[1] == 1:
            x = x.repeat(1,3,1,1)
        x, f1, f2, f3, f4 = self.vmunet(x)
        f1 = f1.permute(0, 3, 1, 2) # f1 [2, 96, 128, 128]
        f2 = f2.permute(0, 3, 1, 2)
        f3 = f3.permute(0, 3, 1, 2)
        f4 = f4.permute(0, 3, 1, 2)
        f1, f2, f3, f4 = self.DCA([f1, f2, f3, f4])
        f1 = f1.permute(0, 2, 3, 1) # f1 [2, 128, 128, 96]
        f2 = f2.permute(0, 2, 3, 1)
        f3 = f3.permute(0, 2, 3, 1)
        f4 = f4.permute(0, 2, 3, 1)
        x = self.vmunet.forward_features_up(x, [f1, f2, f3, f4])
        x = self.vmunet.forward_final(x)
        if self.num_classes == 1: return torch.sigmoid(x)
        else: return x
    
    def load_from(self):
        if self.load_ckpt_path is not None:
            model_dict = self.vmunet.state_dict()
            modelCheckpoint = torch.load(self.load_ckpt_path)
            pretrained_dict = modelCheckpoint['model']
            # 过滤操作
            new_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict.keys()}
            model_dict.update(new_dict)
            # 打印出来，更新了多少的参数
            print('Total model_dict: {}, Total pretrained_dict: {}, update: {}'.format(len(model_dict), len(pretrained_dict), len(new_dict)))
            self.vmunet.load_state_dict(model_dict)

            not_loaded_keys = [k for k in pretrained_dict.keys() if k not in new_dict.keys()]
            print('Not loaded keys:', not_loaded_keys)
            print("encoder loaded finished!")

            model_dict = self.vmunet.state_dict()
            modelCheckpoint = torch.load(self.load_ckpt_path)
            pretrained_odict = modelCheckpoint['model']
            pretrained_dict = {}
            for k, v in pretrained_odict.items():
                if 'layers.0' in k: 
                    new_k = k.replace('layers.0', 'layers_up.3')
                    pretrained_dict[new_k] = v
                elif 'layers.1' in k: 
                    new_k = k.replace('layers.1', 'layers_up.2')
                    pretrained_dict[new_k] = v
                elif 'layers.2' in k: 
                    new_k = k.replace('layers.2', 'layers_up.1')
                    pretrained_dict[new_k] = v
                elif 'layers.3' in k: 
                    new_k = k.replace('layers.3', 'layers_up.0')
                    pretrained_dict[new_k] = v
            # 过滤操作
            new_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict.keys()}
            model_dict.update(new_dict)
            # 打印出来，更新了多少的参数
            print('Total model_dict: {}, Total pretrained_dict: {}, update: {}'.format(len(model_dict), len(pretrained_dict), len(new_dict)))
            self.vmunet.load_state_dict(model_dict)
            
            # 找到没有加载的键(keys)
            not_loaded_keys = [k for k in pretrained_dict.keys() if k not in new_dict.keys()]
            print('Not loaded keys:', not_loaded_keys)
            print("decoder loaded finished!")


if __name__ == '__main__':
    pretrained_path = '../../pre_trained_weights/vmamba_small_e238_ema.pth'
    model = VMUNet(load_ckpt_path=pretrained_path).cuda()
    model.load_from()
    x = torch.randn(2, 3, 512, 512).cuda()
    predict = model(x)
    print(predict.shape)  #  deep_supervision true   predict[0] [2, 1, 256, 256] , predict[1] [2, 1, 128, 128] 这两项用于监督
