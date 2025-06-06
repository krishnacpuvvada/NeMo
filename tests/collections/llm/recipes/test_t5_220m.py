# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import nemo_run as run
import pytest

from nemo.collections.llm.api import finetune, pretrain
from nemo.collections.llm.peft.lora import LoRA
from nemo.collections.llm.recipes import t5_220m
from nemo.collections.llm.t5.data.mock import MockDataModule
from nemo.collections.llm.t5.data.squad import SquadDataModule
from nemo.collections.llm.t5.model.t5 import T5Config220M, T5Model
from nemo.lightning import Trainer


class TestT5_220M:
    @pytest.fixture(scope="class")
    def recipe_module(self):
        return t5_220m

    def test_model(self, recipe_module):
        model_config = recipe_module.model()
        assert isinstance(model_config, run.Config)
        assert model_config.__fn_or_cls__ == T5Model
        assert isinstance(model_config.config, run.Config)
        assert model_config.config.__fn_or_cls__ == T5Config220M

    def test_trainer(self, recipe_module):
        trainer_config = recipe_module.trainer()
        assert isinstance(trainer_config, run.Config)
        assert trainer_config.__fn_or_cls__ == Trainer
        assert trainer_config.accelerator == "gpu"
        assert trainer_config.devices == 8
        assert trainer_config.num_nodes == 1
        assert trainer_config.max_steps == 1000000

        # Check strategy configuration
        assert isinstance(trainer_config.strategy, run.Config)
        assert trainer_config.strategy.__fn_or_cls__.__name__ == "MegatronStrategy"
        assert trainer_config.strategy.tensor_model_parallel_size == 1
        assert trainer_config.strategy.pipeline_model_parallel_size == 1
        assert trainer_config.strategy.pipeline_dtype is None
        assert trainer_config.strategy.virtual_pipeline_model_parallel_size is None
        assert trainer_config.strategy.context_parallel_size == 1
        assert trainer_config.strategy.sequence_parallel is False
        assert trainer_config.strategy.gradient_as_bucket_view is True
        assert trainer_config.strategy.ckpt_async_save is True
        assert trainer_config.strategy.ckpt_parallel_load is True

        # Check other trainer configurations
        assert trainer_config.accumulate_grad_batches == 1
        assert trainer_config.limit_test_batches == 50
        assert trainer_config.limit_val_batches == 32
        assert trainer_config.log_every_n_steps == 10
        assert trainer_config.use_distributed_sampler is False
        assert trainer_config.val_check_interval == 2000

        # Check plugins
        assert isinstance(trainer_config.plugins, run.Config)
        assert trainer_config.plugins.__fn_or_cls__.__name__ == "MegatronMixedPrecision"

    def test_pretrain_recipe(self, recipe_module):
        recipe = recipe_module.pretrain_recipe()
        assert isinstance(recipe, run.Partial)
        assert recipe.__fn_or_cls__ == pretrain
        assert isinstance(recipe.model, run.Config)
        assert recipe.model.__fn_or_cls__ == T5Model
        assert isinstance(recipe.trainer, run.Config)
        assert recipe.trainer.__fn_or_cls__ == Trainer
        assert isinstance(recipe.data, run.Config)
        assert recipe.data.__fn_or_cls__ == MockDataModule
        assert recipe.data.seq_length == 512
        assert recipe.data.seq_length_dec == 128
        assert recipe.data.global_batch_size == 512

    def test_finetune_recipe(self, recipe_module):
        recipe = recipe_module.finetune_recipe()
        assert isinstance(recipe, run.Partial)
        assert recipe.__fn_or_cls__ == finetune
        assert isinstance(recipe.model, run.Config)
        assert recipe.model.__fn_or_cls__ == T5Model
        assert isinstance(recipe.trainer, run.Config)
        assert recipe.trainer.__fn_or_cls__ == Trainer
        assert isinstance(recipe.data, run.Config)
        assert recipe.data.__fn_or_cls__ == SquadDataModule
        assert recipe.data.seq_length == 512
        assert recipe.data.seq_length_dec == 128
        assert recipe.data.global_batch_size == 128
        assert isinstance(recipe.peft, run.Config)
        assert recipe.peft.__fn_or_cls__ == LoRA

    @pytest.mark.parametrize("num_nodes,num_gpus_per_node", [(1, 8), (2, 4), (4, 2)])
    def test_pretrain_recipe_with_different_configurations(self, recipe_module, num_nodes, num_gpus_per_node):
        recipe = recipe_module.pretrain_recipe(num_nodes=num_nodes, num_gpus_per_node=num_gpus_per_node)
        assert recipe.trainer.num_nodes == num_nodes
        assert recipe.trainer.devices == num_gpus_per_node

    def test_trainer_parallelism_options(self, recipe_module):
        trainer_config = recipe_module.trainer(
            tensor_parallelism=2,
            pipeline_parallelism=2,
        )
        assert trainer_config.strategy.tensor_model_parallel_size == 2
        assert trainer_config.strategy.pipeline_model_parallel_size == 2

    def test_model_config_parameters(self, recipe_module):
        model_config = recipe_module.model()
        llama_config = model_config.config
        assert llama_config.num_layers == 12
        assert llama_config.hidden_size == 768
        assert llama_config.ffn_hidden_size == 3072
        assert llama_config.num_attention_heads == 12
