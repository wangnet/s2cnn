#pylint: disable=C,R,E1101
import math
import torch
from torch.nn.parameter import Parameter
from torch.nn.modules import Module

from .gpu.s2_fft import S2_fft_real
from .gpu.so3_fft import SO3_ifft_real
from s2cnn.gpu.s2_mm import S2_mm
from s2cnn import s2_ft

class S2Convolution(Module):
    def __init__(self, nfeature_in, nfeature_out, b_in, b_out, grid):
        '''
        :param nfeature_in: number of input fearures
        :param nfeature_out: number of output features
        :param b_in: input bandwidth (precision of the input SOFT grid)
        :param b_out: output bandwidth
        :param grid: points of the sphere defining the kernel, tuple of (alpha, beta)'s
        '''
        super(S2Convolution, self).__init__()
        self.nfeature_in = nfeature_in
        self.nfeature_out = nfeature_out
        self.b_in = b_in
        self.b_out = b_out
        self.grid = grid
        self.kernel = Parameter(torch.empty(nfeature_in, nfeature_out, len(grid)).uniform_(-1, 1))
        self.scaling = 1. / math.sqrt(len(self.grid) * self.nfeature_in * (self.b_out ** 4.) / (self.b_in ** 2.))
        self.bias = Parameter(torch.zeros(1, nfeature_out, 1, 1, 1))

    def forward(self, x): #pylint: disable=W
        '''
        :x:      [batch, feature_in,  beta, alpha]
        :return: [batch, feature_out, beta, alpha, gamma]
        '''
        assert x.size(1) == self.nfeature_in
        assert x.size(2) == 2 * self.b_in
        assert x.size(3) == 2 * self.b_in
        x = S2_fft_real(b_out=self.b_out)(x) # [l * m, batch, feature_in, complex]
        y = s2_ft(self.kernel * self.scaling, self.b_out, self.grid) # [feature_in, feature_out, l * m, complex]
        y = y.transpose(0, 2) # [l * m, feature_out, feature_in, complex]
        y = y.transpose(1, 2) # [l * m, feature_in, feature_out, complex]
        y = y.contiguous()
        z = S2_mm()(x, y) # [l * m * n, batch, feature_out, complex]
        z = SO3_ifft_real()(z) # [batch, feature_out, beta, alpha, gamma]

        z = z + self.bias

        return z