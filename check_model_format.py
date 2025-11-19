"""
快速检查模型文件格式，判断是否需要转换
"""
import torch
import sys

def check_model_format(model_path):
    """检查模型文件格式"""
    print(f"正在检查模型: {model_path}\n")
    
    try:
        state_dict = torch.load(model_path, map_location='cpu')
        keys = list(state_dict.keys())
        
        print(f"✅ 模型加载成功")
        print(f"   总键数: {len(keys)}")
        print(f"\n前10个键名:")
        for i, key in enumerate(keys[:10]):
            print(f"   {i+1}. {key}")
        
        # 检查格式
        has_backbone_prefix = any(k.startswith('backbone.') for k in keys)
        has_direct_keys = any(k.startswith(('conv1.', 'bn1.', 'layer1.', 'fc.')) for k in keys)
        
        print(f"\n📊 格式分析:")
        if has_backbone_prefix:
            print("   ❌ 检测到 'backbone.' 前缀 - 需要转换！")
            print("   💡 运行: python convert_model.py <模型路径>")
        elif has_direct_keys:
            print("   ✅ 格式正确！键名直接是 ResNet18 的层名")
            print("   ✅ 可以直接用于后端，无需转换")
        else:
            print("   ⚠️  无法确定格式，请检查键名")
        
        # 尝试加载验证
        print(f"\n🔍 兼容性验证:")
        try:
            from torchvision.models import resnet18, ResNet18_Weights
            test_model = resnet18(weights=ResNet18_Weights.DEFAULT)
            test_model.fc = torch.nn.Identity()
            
            missing, unexpected = test_model.load_state_dict(state_dict, strict=False)
            
            if len(missing) == 0 and len(unexpected) == 0:
                print("   ✅ 完美匹配！所有键都能加载")
            else:
                if missing:
                    print(f"   ⚠️  缺少 {len(missing)} 个键: {missing[:3]}...")
                if unexpected:
                    print(f"   ⚠️  多余 {len(unexpected)} 个键: {unexpected[:3]}...")
                print("   💡 使用 strict=False 应该仍可工作")
        except Exception as e:
            print(f"   ⚠️  验证失败: {e}")
        
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {model_path}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_model_format.py <模型文件路径>")
        print("\n示例:")
        print("  python check_model_format.py cat_resnet18.pth")
        print("  python check_model_format.py /kaggle/working/cat_embedding_triplet.pth")
        sys.exit(1)
    
    check_model_format(sys.argv[1])

