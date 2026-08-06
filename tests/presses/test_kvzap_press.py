# SPDX-FileCopyrightText: Copyright (c) 1993-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import torch

from kvpress.presses.kvzap_press import KVzapConfig, KVzapModel


def test_kvzap_model_save_and_load(tmp_path):
    config = KVzapConfig(input_dim=16, output_dim=2, n_modules=3, hidden_dim=4)
    model = KVzapModel(config).eval()
    hidden_states = torch.randn(2, 3, 16)

    with torch.no_grad():
        expected_scores = model(hidden_states)

    model.save_pretrained(tmp_path)
    loaded_model = KVzapModel.from_pretrained(tmp_path, local_files_only=True).eval()

    with torch.no_grad():
        actual_scores = loaded_model(hidden_states)

    assert actual_scores.shape == (2, 3, 2)
    torch.testing.assert_close(actual_scores, expected_scores)
