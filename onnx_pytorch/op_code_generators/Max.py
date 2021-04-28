import onnx
import torch

from onnx_pytorch.op_code_generators import OpCodeGenerator


class MaxOpCodeGenerator(OpCodeGenerator):

  def __init__(self,
               onnx_ver=onnx.defs.onnx_opset_version(),
               torch_ver=torch.__version__):
    super(MaxOpCodeGenerator, self).__init__(onnx_ver, torch_ver)

  def gen(self, node, value_infos, initializers):
    inputs_str, outputs_str = self.gen_input_output_string(node, initializers)
    init_str, forward_str = [], []
    forward_str.append(f"{outputs_str[0]} = torch.max({inputs_str[0]})")
    return {"init": init_str, "forward": forward_str}
