#!/usr/bin/env python
# coding=utf-8
'''
Author: JiangJi
Email: johnjim0816@gmail.com
Date: 2023-12-02 15:02:30
LastEditor: JiangJi
LastEditTime: 2024-06-01 11:34:17
Discription: 
'''
import ray
import copy
import time
from typing import Tuple
import numpy as np
from joyrl.framework.message import Msg, MsgType
from joyrl.framework.config import MergedConfig
from joyrl.framework.base import Moduler
from joyrl.framework.recorder import Recorder
from joyrl.utils.utils import exec_method, create_module

class Learner(Moduler):
    ''' learner
    '''
    def __init__(self, cfg : MergedConfig, **kwargs) -> None:
        super().__init__(cfg, **kwargs)
        self.id = kwargs.get('id', 0)
        self.policy = kwargs.get('policy', None)
        self.policy_mgr = kwargs.get('policy_mgr', None)
        self.collector = kwargs.get('collector', None)
        self.data_handler = kwargs.get('data_handler', None)
        self.tracker = kwargs.get('tracker', None)
        self.recorder = kwargs.get('recorder', None)
        self._raw_exps_que = kwargs.get('raw_exps_que', None)
        self._init_update_steps()

    def _init_update_steps(self):
        if self.cfg.on_policy:
            self.n_update_steps = 1
        else:
            self.n_update_steps = float('inf')

    def run(self):
        run_step = 0
        while True:
            training_data = exec_method(self.collector, 'pub_msg', 'get', Msg(type = MsgType.COLLECTOR_GET_TRAINING_DATA))
            if training_data is not None:
                self.policy.learn(**training_data)
                exec_method(self.tracker, 'pub_msg', 'remote', Msg(type = MsgType.TRACKER_INCREASE_UPDATE_STEP))
                global_update_step = exec_method(self.tracker, 'pub_msg', 'get', Msg(type = MsgType.TRACKER_GET_UPDATE_STEP))
                # put updated model params to policy_mgr
                model_params = self.policy.get_model_params()
                exec_method(self.policy_mgr, 'pub_msg', 'remote', Msg(type = MsgType.POLICY_MGR_PUT_MODEL_PARAMS, data = (global_update_step, model_params)))
                avg_model_step_training_data = np.mean(training_data['model_steps'])
                avg_train_lag = global_update_step - avg_model_step_training_data
                # print(f"[Learner.run] update_step: {global_update_step}, avg_train_lag: {avg_train_lag:.2f}")
                # put policy summary to recorder
                if global_update_step % self.cfg.policy_summary_fre == 0:
                    avg_model_step_training_data = np.mean(training_data['model_steps'])
                    avg_train_lag = global_update_step - avg_model_step_training_data
                    exec_method(self.logger, 'info', 'remote', f"[Learner.run] update_step: {global_update_step}, avg_train_lag: {avg_train_lag:.2f}")
                    policy_summary = self.policy.get_summary()
                    policy_summary.update({'avg_train_lag': avg_train_lag})
                    summary_data = [(global_update_step,self.policy.get_summary())]
                    exec_method(self.recorder, 'pub_msg', 'remote', Msg(type = MsgType.RECORDER_PUT_SUMMARY, data = summary_data))
            run_step += 1
            if run_step >= self.n_update_steps:
                break
    