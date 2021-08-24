import importlib
import inspect
import os
import re

class OptimizerPass(object):
    name = None

    def __init__(self):
        pass

    def match(self, node):
        raise NotImplementedError
    
    def transform(self, model, node):
        raise NotImplementedError
    
    @classmethod
    def get_name(cls):
        if cls.name is None:
            return re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower() # OptimizerPass -> optimizer_pass
        else:
            return cls.name

class GlobalOptimizerPass(OptimizerPass):
    def match(self, node):
        return True # Match everything

class WrappedOptimizerPass(OptimizerPass):
    def __init__(self, name, condition, transform):
        self.name = name
        self.condition = condition
        self.transform_func = transform
    
    def match(self, node):
        return self.condition(node)

    def transform(self, model, node):
        retval = self.transform_func(node)
        return retval if retval is not None else False
    
    def get_name(self):
        return self.name

class LayerOptimizerPass(WrappedOptimizerPass):
    def __init__(self, name, layer_class, transform):
        super(LayerOptimizerPass, self).__init__(name, lambda node: isinstance(node, layer_class), transform)
        self.layer_class = layer_class

def optimizer_pass(condition):
    def decorator(function):
        function._condition = condition
        return function
    return decorator

def extract_optimizers_from_path(opt_path, module_path, initializer=None):
    optimizers = {}

    if not os.path.exists(opt_path):
        return optimizers
    
    if not module_path.endswith('.'):
        module_path += '.'

    for module in os.listdir(opt_path):
        if module == '__init__.py' or module[-3:] != '.py':
            continue
        try:
            lib = importlib.import_module(module_path + module[:-3])
            if 'register_' + module[:-3] in lib.__dict__:
                opt_init_func = lib.__dict__['register_' + module[:-3]]
                if initializer is not None:
                    opt_init_func(initializer)
                else:
                    opt_init_func()
            else:
                for func in list(lib.__dict__.values()):
                    # if 'func' is a class
                    # and it inherits from OptimizerPass
                    # and is defined in this module (i.e., not imported)
                    if inspect.isclass(func) and issubclass(func, OptimizerPass) and func.__module__ == lib.__name__:
                        if inspect.ismethod(func.get_name):
                            optimizers[func.get_name()] = func
                        else:
                            func_instance = func()
                            optimizers[func_instance.get_name()] = func_instance

        except ImportError as e:
            print('WARN: Unable to import optimizer(s) from {}: {}'.format(module, e))
            continue
    
    return optimizers

def extract_optimizers_from_object(clazz):
    optimizers = {}
    optimizer_list = [func for func in dir(clazz) if callable(getattr(clazz, func)) and hasattr(getattr(clazz, func), '_condition')]
    for opt_name in optimizer_list:
        func = getattr(clazz, opt_name)
        if inspect.isclass(func._condition):
            opt = LayerOptimizerPass(name=opt_name, layer_class=func._condition, transform=func)
        else:
            opt = WrappedOptimizerPass(name=opt_name, condition=func._condition, transform=func)
        optimizers[opt_name] = opt
    
    return optimizers

optimizer_map = {}

def _get_backend_name_prefix(name, backend):
    if backend is not None and not name.startswith(backend.lower() + ':'):
        name = backend.lower() + ':' + name

    return name

def register_pass(name, opt_cls, backend=None):
    name = _get_backend_name_prefix(name, backend)

    if name in optimizer_map:
        raise Exception('Optimization pass {} already registered'.format(name))
    
    if inspect.isclass(opt_cls):
        opt = opt_cls()
    else:
        opt = opt_cls

    optimizer_map[name] = opt
    
    return name

def get_optimizer(name):
    if name in optimizer_map:
        return optimizer_map[name]
    else:
        raise Exception('Unknown optimizer: {}'.format(name))

def get_backend_passes(backend):
    return [opt for opt in optimizer_map.keys() if opt.startswith(backend.lower() + ':')]

def get_available_passes():
    return list(optimizer_map.keys())

def optimize_model(model, passes):
    optimizers = [get_optimizer(opt_pass) for opt_pass in passes]
    optimization_done = False
    while not optimization_done:
        for opt in optimizers:
            for node in model.graph.values():
                if opt.match(node):
                    res = opt.transform(model, node)
                    if res:
                        break
            else:
                continue
            break
        else:
            optimization_done = True
