# Copyright (c) OpenMMLab. All rights reserved.
from argparse import ArgumentParser

from mmseg.apis import inference_segmentor, init_segmentor, show_result_pyplot

import os
import glob
from tqdm import tqdm
import numpy as np

def main():
    parser = ArgumentParser()
    parser.add_argument('datset', help='Image file')
    parser.add_argument('--config', default="./data_utils/easyportrait/local_configs/easyportrait_experiments_v2/fpn-fp/fpn-fp.py", help='Config file')
    parser.add_argument('--checkpoint', default="./data_utils/easyportrait/fpn-fp-512.pth", help='Checkpoint file')

    args = parser.parse_args()

    # build the model from a config file and a checkpoint file
    model = init_segmentor(args.config, args.checkpoint, device='cuda:0')

    # test a single image
    dataset_path = os.path.join(args.datset, 'ori_imgs')
    out_path = os.path.join(args.datset, 'teeth_mask')
    os.makedirs(out_path, exist_ok=True)

    for file in tqdm(glob.glob(os.path.join(dataset_path, '*.jpg'))):
        result = inference_segmentor(model, file)
        result[0][result[0]!=7] = 0
        np.save(file.replace('jpg', 'npy').replace('ori_imgs', 'teeth_mask'), result[0].astype(np.bool_))


if __name__ == '__main__':
    # ---- PyTorch 2.6 兼容补丁：强制 torch.load(weights_only=False) ----
    import builtins  # 仅保证位置在最顶，避免后面的 import 提前触发 torch.load

    import torch as _torch

    _orig_load = _torch.load


    def _patched_load(*args, **kwargs):
        # 关键：显式回退到旧行为
        kwargs.setdefault("weights_only", False)
        return _orig_load(*args, **kwargs)


    _torch.load = _patched_load
    # ------------------------------------------------------------------

    import numpy as np
    from torch.serialization import add_safe_globals

    # 允许旧 checkpoint 中常见的 numpy 对象
    add_safe_globals([np.core.multiarray.scalar])

    main()
