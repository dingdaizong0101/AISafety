import numpy as np
import torch
import math
import torch.utils.data as Data
from torch.autograd import Variable

from EvalBox.Evaluation.evaluation import Evaluation
from EvalBox.Evaluation.evaluation import MIN_COMPENSATION

class TKNP(Evaluation):
    def __init__(self, outputs_origin,outputs_adv, device, model, **kwargs):
        '''
        @description:
        @param {
            model:
            device:
            kwargs:
        }
        @return: None
        '''
        super(TKNP, self).__init__(outputs_origin,outputs_adv, device)
        self.model = model
        self._parsing_parameters(**kwargs)

    def _parsing_parameters(self, **kwargs):
        '''
        @description: 
        @param {
            batch_size:
        } 
        @return: 
        '''
        self.batch_size = kwargs.get('batch_size', 64)
        self.module_name = []
        self.upper_feature_map = []
        self.lower_feature_map = []
        self.tknc_feature_map = []
        self.features_out_hook = []
        self.knum = 2

    def for_hook(self, module, fea_in, fea_out):
        self.features_out_hook.append(fea_out.data.cpu().numpy())

    def output_hook(self):
        print("*"*5+"hook record features"+"*"*5)
        for i in range(len(self.module_name)):
            print(self.module_name[i])
            print(self.features_out_hook[i].size())
        print("*"*5+"hook record features"+"*"*5)

    def evaluate(self,adv_xs=None, cln_xs=None, cln_ys=None,adv_ys=None,target_preds=None, target_flag=False):
        '''
        @description:
        @param {
            adv_xs: 攻击样本
            cln_xs：原始样本
            cln_ys: 原始类别，非目标攻击下原始样本的类型
            adv_ys: 攻击样本的预测类别
            target_preds： 目标攻击下希望原始样本攻击的目标类别
            target_flag：是否是目标攻击
        }
        @return: tknc {}
        '''
        #print("target_flag",target_flag)
        total = len(adv_xs)
        print("total",total)
        device = self.device
        assert len(adv_xs) == len(adv_ys), 'examples and labels do not match.'

        # 监听所有中间层特征
        hook_handle_list = []
        for name, module in self.model._modules.items():
            self.module_name.append(name)
            handle = module.register_forward_hook(self.for_hook)
            hook_handle_list.append(handle)

        adv_dataset = Data.TensorDataset(adv_xs, adv_ys)
        adv_loader = Data.DataLoader(adv_dataset, batch_size=self.batch_size, num_workers=3)

        for x, y in adv_loader:
            x, y = Variable(x.to(device)), Variable(y.to(device))
            with torch.no_grad():
                pred = self.model(x)

        for handle in hook_handle_list:
            handle.remove()

        # 输出feature map =  feature_num * N * neuron_num * output
        # self.output_feature_map()
        
        tknp_list = [[] for i in range(total)]
        
        # key表示特征名
        for key in range(len(self.module_name)):
            # k 表示第k个测试样本
            layer_pattern = []
            for k in range(len(self.features_out_hook[key])):
                # c表示第c个神经元
                layer_output = []
                for c in range(len(self.features_out_hook[key][k])):
                    # x表示key层的神经元c在第k个测试时的输出结果
                    x = np.mean(self.features_out_hook[key][k][c])
                    layer_output.append(x)
                layer_output = np.array(layer_output)
                k_num = self.knum
                if k_num > len(self.features_out_hook[key][k]):
                    k_num = len(self.features_out_hook[key][k])
                topk = layer_output.argsort()[-k_num:][::-1]
                topk.sort()
                tknp_list[k].extend(topk)
        return len(set([tuple(t) for t in tknp_list]))