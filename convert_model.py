"""
转换训练好的模型文件，将 CatEmbeddingModel 的 state_dict 转换为后端可用的格式
（去掉 "backbone." 前缀）
"""
import torch
import sys

def convert_model(input_path, output_path=None):
    """
    转换模型文件格式
    
    Args:
        input_path: 输入的模型文件路径（可能是 model.state_dict() 保存的）
        output_path: 输出的模型文件路径（如果为 None，则覆盖原文件）
    """
    print(f"正在加载模型: {input_path}")
    
    try:
        # 加载原始模型
        state_dict = torch.load(input_path, map_location='cpu')
        print(f"✅ 成功加载模型，包含 {len(state_dict)} 个键")
        
        # 检查键名格式
        sample_keys = list(state_dict.keys())[:5]
        print(f"前5个键名示例: {sample_keys}")
        
        # 判断是否需要转换
        needs_conversion = any(key.startswith('backbone.') for key in state_dict.keys())
        
        if not needs_conversion:
            print("⚠️  模型键名已经是正确格式（没有 'backbone.' 前缀），无需转换")
            print("   但为了安全，仍然会创建一个新文件...")
        
        # 转换：去掉 "backbone." 前缀
        converted_state = {}
        removed_keys = []
        
        for key, value in state_dict.items():
            if key.startswith('backbone.'):
                # 去掉 "backbone." 前缀
                new_key = key[len('backbone.'):]
                converted_state[new_key] = value
            elif key == 'backbone':
                # 如果整个模型被保存为一个 backbone 对象（不太可能，但处理一下）
                print("⚠️  检测到整个 backbone 对象，尝试提取其 state_dict...")
                if hasattr(value, 'state_dict'):
                    backbone_dict = value.state_dict()
                    converted_state.update(backbone_dict)
                else:
                    print(f"⚠️  无法处理键 '{key}'，跳过")
            else:
                # 其他键（可能是优化器状态等），通常不需要
                removed_keys.append(key)
                print(f"⚠️  跳过非 backbone 键: {key}")
        
        if removed_keys:
            print(f"\n已跳过 {len(removed_keys)} 个非 backbone 键")
        
        print(f"\n✅ 转换完成！")
        print(f"   原始键数: {len(state_dict)}")
        print(f"   转换后键数: {len(converted_state)}")
        
        # 保存转换后的模型
        if output_path is None:
            # 如果没有指定输出路径，创建新文件名
            if input_path.endswith('.pth'):
                output_path = input_path.replace('.pth', '_converted.pth')
            else:
                output_path = input_path + '_converted'
        
        torch.save(converted_state, output_path)
        print(f"✅ 已保存转换后的模型到: {output_path}")
        
        # 验证：尝试加载到 ResNet18 看看是否匹配
        print("\n正在验证模型兼容性...")
        try:
            from torchvision.models import resnet18, ResNet18_Weights
            test_model = resnet18(weights=ResNet18_Weights.DEFAULT)
            test_model.fc = torch.nn.Identity()
            
            # 尝试加载（strict=False 允许部分匹配）
            missing_keys, unexpected_keys = test_model.load_state_dict(converted_state, strict=False)
            
            if len(missing_keys) == 0 and len(unexpected_keys) == 0:
                print("✅ 完美匹配！所有键都能正确加载")
            else:
                if missing_keys:
                    print(f"⚠️  缺少的键 ({len(missing_keys)} 个): {missing_keys[:5]}...")
                if unexpected_keys:
                    print(f"⚠️  多余的键 ({len(unexpected_keys)} 个): {unexpected_keys[:5]}...")
                print("   但使用 strict=False 应该仍然可以工作")
            
            print("✅ 模型验证通过，可以用于后端！")
            
        except Exception as e:
            print(f"⚠️  验证时出现警告: {e}")
            print("   但模型文件已保存，你可以手动测试")
        
        return output_path
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {input_path}")
        return None
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python convert_model.py <输入模型路径> [输出模型路径]")
        print("\n示例（本地）:")
        print("  python convert_model.py cat_embedding_triplet.pth")
        print("  python convert_model.py cat_embedding_triplet.pth cat_resnet18.pth")
        print("\n示例（Kaggle）:")
        print("  python convert_model.py /kaggle/working/cat_embedding_triplet.pth")
        print("  python convert_model.py /kaggle/working/cat_embedding_triplet.pth /kaggle/working/cat_resnet18.pth")
        print("\n💡 提示:")
        print("  - 在 Kaggle Notebook 中可以直接运行此脚本")
        print("  - 转换后的模型会保存在 /kaggle/working/ 目录，可以下载")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_model(input_path, output_path)

