from hls4ml.model.flow.flow import register_flow
import os

from hls4ml.model.optimizer.optimizer import OptimizerPass, GlobalOptimizerPass, LayerOptimizerPass, register_pass, get_optimizer, optimize_model, get_available_passes, get_backend_passes, optimizer_pass, extract_optimizers_from_path, extract_optimizers_from_object


opt_path = os.path.dirname(__file__) + '/passes'
module_path = __name__ + '.passes'

optimizers = extract_optimizers_from_path(opt_path, module_path)
for opt_name, opt in optimizers.items():
    register_pass(opt_name, opt)

register_flow('convert', ['fuse_bias_add', 'output_rounding_saturation_mode', 'qkeras_factorize_alpha', 'fuse_consecutive_batch_normalization']) # TODO Maybe not all QKeras optmizers belong here?
register_flow('optimize', ['eliminate_linear_activation', 'fuse_batch_normalization'], requires=['convert'])

del opt_path
del module_path
del optimizers
