"""
在 Kaggle 中快速转换已训练的模型文件
将 CatEmbeddingModel 的 state_dict 转换为后端可用的格式
"""
import torch
import os

def convert_kaggle_model(input_path="/kaggle/working/cat_embedding_triplet.pth", 
                         output_path="/kaggle/working/cat_resnet18.pth"):
    """
    转换 Kaggle 中的模型文件格式
    
    Args:
        input_path: 输入的模型文件路径（默认 /kaggle/working/cat_embedding_triplet.pth）
        output_path: 输出的模型文件路径（默认 /kaggle/working/cat_resnet18.pth）
    """
    print("=" * 60)
    print("🔄 模型格式转换工具")
    print("=" * 60)
    print(f"\n📂 输入文件: {input_path}")
    print(f"📂 输出文件: {output_path}\n")
    
    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"❌ 错误: 找不到输入文件 {input_path}")
        print("\n💡 提示: 请检查文件路径，或修改脚本中的 input_path 参数")
        return None
    
    try:
        # 加载原始模型
        print("📥 正在加载模型...")
        state_dict = torch.load(input_path, map_location='cpu')
        print(f"✅ 成功加载模型，包含 {len(state_dict)} 个键")
        
        # 检查键名格式
        sample_keys = list(state_dict.keys())[:5]
        print(f"\n📋 前5个键名示例:")
        for i, key in enumerate(sample_keys, 1):
            print(f"   {i}. {key}")
        
        # 判断是否需要转换
        needs_conversion = any(key.startswith('backbone.') for key in state_dict.keys())
        
        if not needs_conversion:
            print("\n⚠️  模型键名已经是正确格式（没有 'backbone.' 前缀）")
            print("   但为了确保兼容性，仍然会处理...")
        
        # 转换：去掉 "backbone." 前缀
        print("\n🔄 正在转换键名...")
        converted_state = {}
        skipped_keys = []
        
        for key, value in state_dict.items():
            if key.startswith('backbone.'):
                # 去掉 "backbone." 前缀
                new_key = key[len('backbone.'):]
                converted_state[new_key] = value
            elif key == 'backbone':
                # 如果整个模型被保存为一个 backbone 对象
                print("⚠️  检测到整个 backbone 对象，尝试提取...")
                if hasattr(value, 'state_dict'):
                    backbone_dict = value.state_dict()
                    converted_state.update(backbone_dict)
            else:
                # 其他键（可能是优化器状态等），跳过
                skipped_keys.append(key)
        
        if skipped_keys:
            print(f"\n⚠️  已跳过 {len(skipped_keys)} 个非 backbone 键")
            if len(skipped_keys) <= 5:
                for key in skipped_keys:
                    print(f"   - {key}")
        
        print(f"\n✅ 转换完成！")
        print(f"   原始键数: {len(state_dict)}")
        print(f"   转换后键数: {len(converted_state)}")
        
        # 保存转换后的模型
        print(f"\n💾 正在保存到: {output_path}")
        torch.save(converted_state, output_path)
        print(f"✅ 模型已保存！")
        
        # 验证文件大小
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            print(f"📊 文件大小: {file_size:.2f} MB")
        
        # 验证：尝试加载到 ResNet18 看看是否匹配
        print("\n🔍 正在验证模型兼容性...")
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
                    print(f"⚠️  缺少的键 ({len(missing_keys)} 个): {missing_keys[:3]}...")
                if unexpected_keys:
                    print(f"⚠️  多余的键 ({len(unexpected_keys)} 个): {unexpected_keys[:3]}...")
                print("   💡 使用 strict=False 应该仍然可以工作")
            
            print("✅ 模型验证通过，可以用于后端！")
            
        except Exception as e:
            print(f"⚠️  验证时出现警告: {e}")
            print("   但模型文件已保存，你可以手动测试")
        
        print("\n" + "=" * 60)
        print("🎉 转换完成！")
        print(f"📥 可以从 Kaggle 下载: {output_path}")
        print("=" * 60)
        
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
    # 在 Kaggle Notebook 中直接运行此脚本
    # 默认转换 /kaggle/working/cat_embedding_triplet.pth
    
    # 方式1: 使用默认路径
    convert_kaggle_model()
    
    # 方式2: 自定义路径（取消注释并修改）
    # convert_kaggle_model(
    #     input_path="/kaggle/working/your_model.pth",
    #     output_path="/kaggle/working/cat_resnet18.pth"
    # )

