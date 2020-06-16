import torch
from torch import nn

from deeplio.common.logger import get_app_logger
from .base_net import BaseNet
from ..misc import get_config_container

class BaseDeepLIO(BaseNet):
    """
    Base network for just main modules, e.g. deepio, deeplo and deeplios
    """
    def __init__(self):
        super(BaseDeepLIO, self).__init__()
        self.cfg_container = get_config_container()
        self.seq_size = self.cfg_container.seq_size
        self.combinations = self.cfg_container.combinations
        self.output_shape = None

    def get_feat_networks(self):
        raise NotImplementedError()

    def initialize(self):
        raise NotImplementedError()


class DeepLIO(BaseDeepLIO):
    """Base class for all DepplioN Networks"""
    def __init__(self, input_shape, cfg, bn_d=0.1):
        super(DeepLIO, self).__init__()

        self.logger = get_app_logger()
        self.cfg = cfg['deeplio']
        self.p = self.cfg.get('dropout', 0.)
        self.input_shape = input_shape

        self.lidar_feat_net = None
        self.imu_feat_net = None
        self.fusion_net = None
        self.odom_feat_net = None

        self.drop = None
        self.fc_pos = None
        self.fc_ori = None
        self.feat_nets = None

    def initialize(self):
        self.feat_nets = [self.odom_feat_net, self.fusion_net, self.imu_feat_net, self.lidar_feat_net]
        last_layer = None
        for net in self.feat_nets:
            if net is not None:
                last_layer = net
                break

        in_shape = last_layer.get_output_shape()[2] # [N]

        if self.p > 0:
            self.drop = nn.Dropout(self.p)
        self.fc_pos = nn.Linear(in_shape, 3)
        self.fc_ori = nn.Linear(in_shape, 4)

    def forward(self, x):
        lidar_imgs = x[0]  # lidar image frames
        imu_meas = x[1]  # imu measurments
        x_last_feat = None

        x_feat_lidar = None
        if self.lidar_feat_net is not None:
            x_feat_lidar = self.lidar_feat_net(lidar_imgs)
            x_last_feat = x_feat_lidar

        x_feat_imu = None
        if self.imu_feat_net is not None:
            x_feat_imu = self.imu_feat_net(imu_meas)
            x_last_feat = x_feat_imu

        x_fusion = None
        if self.fusion_net is not None:
            x_fusion = self.fusion_net([x_feat_lidar, x_feat_imu])
            x_last_feat = x_fusion

        x_odom = None
        if self.odom_feat_net is not None:
            x_odom = self.odom_feat_net(x_last_feat)
            x_last_feat = x_odom

        b, s = x_last_feat.shape[0:2]
        x_last_feat = x_last_feat.reshape(b*s, -1)
        if self.p > 0.:
            x_last_feat = self.drop(x_last_feat)

        x_pos = self.fc_pos(x_last_feat)
        x_ori = self.fc_ori(x_last_feat)
        return x_pos, x_ori

    def get_feat_networks(self):
        nets = []
        for net in self.feat_nets:
            if net is not None:
                nets.append(net)
        return nets


class DeepLIOFusionLayer():
    def __init__(self, input_shapes, cfg):
        """
        :param input_shapes: the inputshape of the layers of dim = [[BxN_0],...,[BxN_i]
        :param cfg:
        """
        self.cfg_container = get_config_container()
        self.seq_size = self.cfg_container.seq_size
        self.combinations = self.cfg_container.combinations
        self.type = cfg.get('type', 'cat').lower()
        self.input_shapes = input_shapes

        n = [input[2] for input in self.input_shapes]
        self.output_shape = [1, self.seq_size, sum(n)]

    def forward(self, x):
        lidar_feat = x[0]
        imu_feat = x[1]
        if self.type == 'cat':
            out = torch.cat((lidar_feat, imu_feat), dim=2)
        else:
            raise NotImplementedError()
        return out

    def get_output_shape(self):
        return self.output_shape

    def __call__(self, x):
        return self.forward(x)


