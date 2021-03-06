import torch.nn as nn
import torch
import math
import torch.utils.model_zoo as model_zoo

__all__ = ['XResNet', 'xresnet18', 'xresnet34', 'xresnet50', 'xresnet101', 'xresnet152']

def init_cnn(m):
    if isinstance(m, nn.Conv2d):
        nn.init.kaiming_normal_(m.weight)
        if getattr(m, 'bias', None) is not None: nn.init.constant_(m.bias, 0)
    elif isinstance(m, nn.BatchNorm2d):
        nn.init.constant_(m.weight, 1)
        nn.init.constant_(m.bias, 0)
    for l in m.children(): init_cnn(l)

def conv(ni, nf, ks=3, stride=1, bias=False):
    return nn.Conv2d(ni, nf, kernel_size=ks, stride=stride, padding=ks//2, bias=bias)

def conv_relu_bn_(ni, nf, ks=3, stride=1, rev=False):
    layers = [conv(ni, nf, ks, stride=stride),
        nn.ReLU(inplace=True),
        nn.BatchNorm2d(ni if rev else nf)]
    if rev: layers = reversed(layers)
    return layers

def conv_bn_relu(ni, nf, ks=3, stride=1):
    return nn.Sequential(*conv_relu_bn_(ni, nf, ks=ks, stride=stride))

def bn_relu_conv(ni, nf, ks=3, stride=1):
    return nn.Sequential(*conv_relu_bn_(ni, nf, ks=ks, stride=stride, rev=True))

class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, ni, nf, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = bn_relu_conv(ni, nf, stride=stride)
        self.conv2 = bn_relu_conv(nf, nf)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x if self.downsample is None else self.downsample(x)
        x = self.conv1(x)
        x = self.conv2(x)
        x += identity
        return x

class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, ni, nf, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = bn_relu_conv(ni, nf, 1)
        self.conv2 = bn_relu_conv(nf, nf, stride=stride)
        self.conv3 = bn_relu_conv(nf, nf * self.expansion, 1)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x if self.downsample is None else self.downsample(x)
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x += identity
        return x

class XResNet(nn.Module):

    def __init__(self, block, layers, num_classes=1000):
        self.ni = 64
        super().__init__()
        self.conv1 = conv_bn_relu(3, 32, stride=2)
        self.conv2 = conv_bn_relu(32, 32)
        self.conv3 = conv(32, 64)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        ni = 512*block.expansion
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(ni),
            nn.Linear(ni, num_classes))

        init_cnn(self)

        for m in self.modules():
            if isinstance(m, BasicBlock): nn.init.constant_(m.conv2[0].weight, 0.)
            if isinstance(m, Bottleneck): nn.init.constant_(m.conv3[0].weight, 0.)
            if isinstance(m, nn.Linear): m.weight.data.normal_(0, 0.01)

    def _make_layer(self, block, nf, blocks, stride=1):
        downsample = None
        if stride != 1 or self.ni != nf*block.expansion:
            layers = []
            if stride==2: layers.append(nn.AvgPool2d(kernel_size=2, stride=2))
            layers += [
                conv(self.ni, nf*block.expansion, 1),
                nn.BatchNorm2d(nf * block.expansion) ]
            downsample = nn.Sequential(*layers)

        layers = []
        layers.append(block(self.ni, nf, stride, downsample))
        self.ni = nf * block.expansion
        for i in range(1, blocks): layers.append(block(self.ni, nf))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x

model_urls = dict(xresnet34='xresnet34', xresnet50='xresnet50')

def xresnet(block, n_layers, name, pre=False, **kwargs):
    model = XResNet(block, n_layers, **kwargs)
    #if pre: model.load_state_dict(model_zoo.load_url(model_urls[name]))
    if pre: model.load_state_dict(torch.load(model_urls[name]))
    return model

def xresnet18(pretrained=False, **kwargs):
    return xresnet(BasicBlock, [2, 2, 2, 2], 'xresnet18', pre=pretrained, **kwargs)

def xresnet34(pretrained=False, **kwargs):
    return xresnet(BasicBlock, [3, 4, 6, 3], 'xresnet34', pre=pretrained, **kwargs)

def xresnet50(pretrained=False, **kwargs):
    return xresnet(Bottleneck, [3, 4, 6, 3], 'xresnet50', pre=pretrained, **kwargs)

def xresnet101(pretrained=False, **kwargs):
    return xresnet(Bottleneck, [3, 4, 23, 3], 'xresnet101', pre=pretrained, **kwargs)

def xresnet152(pretrained=False, **kwargs):
    return xresnet(Bottleneck, [3, 8, 36, 3], 'xresnet152', pre=pretrained, **kwargs)

