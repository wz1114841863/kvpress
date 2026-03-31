# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass, field
from typing import Literal, Optional

import torch
import torch.nn as nn
from transformers import PretrainedConfig, PreTrainedModel

from kvpress.presses.scorer_press import ScorerPress


class KVzapConfig(PretrainedConfig):
    model_type: str = "kvzap"
    input_dim: int = 0
    output_dim: int = 0
    hidden_dim: Optional[int] = None
    n_modules: int = 0


class KVzapModel(PreTrainedModel):
    config_class = KVzapConfig  # type: ignore[assignment]

    def __init__(self, config):
        super().__init__(config)
        self.all_tied_weights_keys = {}
        if config.hidden_dim is None:
            # Linear model
            self.layers = nn.ModuleList(
                [nn.Linear(config.input_dim, config.output_dim) for _ in range(config.n_modules)]
            )
        else:
            # 2-layer MLP model
            self.layers = nn.ModuleList(
                nn.Sequential(
                    nn.Linear(config.input_dim, config.hidden_dim),
                    nn.GELU(),
                    nn.Linear(config.hidden_dim, config.output_dim),
                )
                for _ in range(config.n_modules)
            )

    def forward(self, x):
        """输入 x 的形状预期为 (batch_size, n_modules, input_dim).
        代码遍历所有的打分模块,将第i层的隐藏状态 x[:, i, :] 传入第i$个模块进行打分,最后用 torch.stack 将各层结果拼接起来.
        这个 forward 方法主要用于模型训练阶段.在实际推理时,使用的是下面的 KVzapPress.score 方法
        """
        return torch.stack([module(x[:, i, :]) for i, module in enumerate(self.layers)], dim=1)


@dataclass
class KVzapPress(ScorerPress):
    """
    KVzap (https://arxiv.org/abs/2601.07891) is a fast approximation of KVzip that works
    in both prefilling and decoding. It applies a lightweight surrogate model to the hidden
    states to predict importance scores for every KV pair.
    KVzapPress is designed to be used in conjunction with the DMSPress
    model_type can be "linear" or "mlp".
    """

    model_type: Literal["linear", "mlp"] = "mlp"  # 定义代理网络的类型
    kvzap_model_name: Optional[str] = field(default=None, init=False)

    def post_init_from_model(self, model):
        """根据主模型的配置动态加载KVzap模型"""
        # 根据模型名称来选择是下载还是虚拟构建
        if model.config.name_or_path.endswith("0.5B"):
            self.post_init_from_model_debug(model)
            return

        kvzap_model_name = f"nvidia/KVzap-{self.model_type}-{model.config.name_or_path.split('/')[-1]}"
        if kvzap_model_name != self.kvzap_model_name:
            self.kvzap_model_name = kvzap_model_name
            self.kvzap_model = KVzapModel.from_pretrained(self.kvzap_model_name)

    def post_init_from_model_debug(self, model):
        """[调试专用]动态生成一个随机权重的哑巴代理网络"""
        print("\n[Debug] 正在生成随机权重的 KVzap 代理网络,仅供流程调试使用...\n")

        # 1. 从你的 0.5B 模型中提取真实的结构参数
        hidden_size = model.config.hidden_size
        # 兼容不同模型的 head 命名
        num_kv_heads = getattr(model.config, "num_key_value_heads", model.config.num_attention_heads)
        num_layers = model.config.num_hidden_layers

        # 2. 手动组装一个配置
        dummy_config = KVzapConfig(
            model_type="kvzap",
            input_dim=hidden_size,
            output_dim=num_kv_heads,
            hidden_dim=hidden_size // 2 if self.model_type == "mlp" else None,
            n_modules=num_layers,
        )

        # 3. 直接初始化模型(不调用 from_pretrained),此时全是随机初始化的无意义权重
        self.kvzap_model = KVzapModel(dummy_config)

        # 4. 把这个随机网络搬到和主模型同样的显卡和精度上
        self.kvzap_model.to(model.device, dtype=model.dtype)

    def score(
        self,
        module: nn.Module,
        hidden_states: torch.Tensor,
        keys: torch.Tensor,
        values: torch.Tensor,
        attentions: torch.Tensor,
        kwargs: dict,
    ) -> torch.Tensor:
        # 获取当前 LLM 层对应的特定打分器模块,并将隐藏状态传入该模块进行打分
        kvzap_module = self.kvzap_model.layers[module.layer_idx]
        # 确保打分器和当前隐藏状态在同一个设备和数据类型上,并处于评估模式.
        kvzap_module = kvzap_module.to(hidden_states.device, dtype=hidden_states.dtype).eval()
        # 将当前的隐藏状态输入代理网络,输出分数.
        # 假设输入形状为 (batch, seq_len, input_dim),输出形状则为 (batch, seq_len, num_heads).
        # 将形状转换为 (batch, num_heads, seq_len),以匹配标准 Attention 机制的维度习惯,随后返回这些分数.
        # kvpress 框架会根据这些分数决定保留或丢弃哪些 KV 缓存.
        scores = kvzap_module(hidden_states).transpose(1, 2)
        return scores
