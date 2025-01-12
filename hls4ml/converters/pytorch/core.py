from hls4ml.converters.pytorch_to_hls import get_weights_data, pytorch_handler


@pytorch_handler('Linear')
def parse_linear_layer(operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config):
    assert 'Linear' in operation

    layer = {}

    layer['class_name'] = 'Dense'
    layer['name'] = layer_name

    layer['weight_data'], layer['bias_data'] = get_weights_data(data_reader, layer['name'], ['weight', 'bias'])
    if class_object is not None:
        layer['n_in'] = class_object.in_features
        layer['n_out'] = class_object.out_features
    else:
        raise Exception('parsing of torch.nn.functional.linear not supported yet, please use torch.nn.Linear class')

    # Handling whether bias is used or not
    if class_object.bias is None:
        layer['use_bias'] = False
    else:
        layer['use_bias'] = True

    output_shape = input_shapes[0][:]
    output_shape[-1] = layer['n_out']

    return layer, output_shape


activation_layers = ['Softmax', 'ReLU', 'LeakyReLU', 'Threshold', 'ELU', 'PReLU', 'Sigmoid', 'Tanh']


@pytorch_handler(*activation_layers)
def parse_activation_layer(operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config):
    layer = {}

    layer['class_name'] = operation
    layer['activation'] = layer['class_name']
    layer['name'] = layer_name

    # if layer['class_name'] != 'Activation':
    #    layer['activation'] = layer['class_name']
    if node.op == 'call_module':
        if layer['class_name'] == 'ReLU' or layer['class_name'] == 'Sigmoid':
            layer['class_name'] = 'Activation'
        if layer['class_name'] == 'LeakyReLU':
            layer['activ_param'] = class_object.negative_slope
        if layer['class_name'] == 'ELU':
            layer['activ_param'] = class_object.alpha
        if layer['class_name'] == 'PReLU':
            layer['alpha_data'] = get_weights_data(data_reader, layer['name'], 'weight')
        if layer['class_name'] == 'Threshold':
            layer['activ_param'] = class_object.threshold
            layer['class_name'] = 'ThresholdedReLU'
            layer['activation'] = 'ThresholdedReLU'
            if layer['activ_param'] < 0:
                raise Exception('negative threshold values not supported')

        if hasattr(node, 'dim'):
            layer['axis'] = class_object.dim
    else:
        if layer['class_name'] == 'ReLU' or layer['class_name'] == 'Sigmoid':
            layer['class_name'] = 'Activation'
        if layer['class_name'] == 'LeakyReLU':
            layer['activ_param'] = node.kwargs['negative_slope']
        if layer['class_name'] == 'ELU':
            layer['activ_param'] = node.kwargs['alpha']
        if layer['class_name'] == 'Threshold':
            layer['activ_param'] = node.args[1]
            if layer['activ_param'] < 0:
                raise Exception('negative threshold values not supported')
            layer['class_name'] = 'ThresholdedReLU'
            layer['activation'] = 'ThresholdedReLU'
        if 'dim' in node.kwargs:
            layer['axis'] = node.kwargs['dim']

    output_shape = input_shapes[0]
    return layer, output_shape


batchnorm_layers = ['BatchNorm2d', 'BatchNorm1d', 'Batch_norm']


@pytorch_handler(*batchnorm_layers)
def parse_batchnorm_layer(operation, layer_name, input_names, input_shapes, node, class_object, data_reader, config):
    assert 'BatchNorm' in operation

    layer = {}

    layer['class_name'] = 'BatchNormalization'
    layer['data_format'] = 'channels_first'
    layer['name'] = layer_name

    # batchnorm para
    if node.op == 'call_module':
        layer['epsilon'] = class_object.eps
        layer['use_gamma'] = layer['use_beta'] = class_object.affine

        if layer['use_gamma']:
            layer['gamma_data'] = get_weights_data(data_reader, layer['name'], 'weight')
        else:
            layer['gamma_data'] = 1

        if layer['use_beta']:
            layer['beta_data'] = get_weights_data(data_reader, layer['name'], 'bias')
        else:
            layer['beta_data'] = 0

        layer['mean_data'], layer['variance_data'] = get_weights_data(
            data_reader, layer['name'], ['running_mean', 'running_var']
        )
    in_size = 1
    for dim in input_shapes[0][1:]:
        in_size *= dim

    layer['n_in'] = layer['n_out'] = in_size

    if len(input_shapes[0]) == 2:
        layer['n_filt'] = -1
    elif len(input_shapes[0]) > 2:
        layer['n_filt'] = input_shapes[0][1]  # Always channel first for Pytorch

    return layer, [shape for shape in input_shapes[0]]
