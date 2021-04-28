import onnx
import torch
from onnx.numpy_helper import to_array

from onnx_pytorch.op_code_generators import OpCodeGenerator


class ReduceSumOpCodeGenerator(OpCodeGenerator):

  def __init__(self,
               onnx_ver=onnx.defs.onnx_opset_version(),
               torch_ver=torch.__version__):
    super(ReduceSumOpCodeGenerator, self).__init__(onnx_ver, torch_ver)

  def gen(self, node, value_infos, initializers):
    attr_value_dict = self.get_attr_value_dict(node)
    inputs_str, outputs_str = self.gen_input_output_string(node, initializers)
    init_str, forward_str = [], []
    d = len(value_infos[node.input[0]].type.tensor_type.shape.dim)
    dim = list(range(d))
    if len(node.input) > 1:
      dim = initializers.get(node.input[1], None)
      assert dim is not None, "Currently ReduceSumOpCodeGenerator only support all of [axes] is in initializers."
      dim = list(to_array(dim))

    dim = attr_value_dict["axes"]
    params_str = self.gen_params_str(keepdim=bool(attr_value_dict["keepdims"]))
    forward_str.append(
        f"{outputs_str[0]} = torch.sum({inputs_str[0]}, tuple({dim.__repr__()}), **{{{params_str}}})"
    )
    return {"init": init_str, "forward": forward_str}
