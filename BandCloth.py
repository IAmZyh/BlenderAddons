bl_info = {
    "name": "服装绑定",
    "author": "航于崢",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "3D视图 > 侧边栏 > 骨骼工具",
    "description": "为选中的两个骨架中同名骨骼添加复制变换约束，适用于给服装骨骼绑定给身体骨骼",
    "category": "动画",
}

import bpy

class BONE_OT_copy_transforms_between_armatures(bpy.types.Operator):
    """为两个骨架中同名骨骼添加复制变换约束"""
    bl_idname = "bone.add_copy_transforms_between_armatures"
    bl_label = "添加同名骨骼复制变换约束"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 获取选中的物体
        selected_objects = context.selected_objects
        active_object = context.active_object

        # 验证选中的是两个骨架
        armatures = [obj for obj in selected_objects if obj.type == 'ARMATURE']
        
        if len(armatures) != 2:
            self.report({'ERROR'}, "请精确选中两个不同的骨架物体！")
            return {'CANCELLED'}
        
        if active_object not in armatures or active_object.type != 'ARMATURE':
            self.report({'ERROR'}, "活动对象必须是其中一个骨架！")
            return {'CANCELLED'}
        
        # 区分活动骨架和目标骨架
        active_armature = active_object
        # 找到另一个骨架作为目标骨架
        target_armature = [arm for arm in armatures if arm != active_armature][0]
        
        if active_armature == target_armature:
            self.report({'ERROR'}, "请选择两个不同的骨架！")
            return {'CANCELLED'}
        
        # 进入编辑模式获取骨骼列表（确保能获取所有骨骼名称）
        bpy.context.view_layer.objects.active = active_armature
        bpy.ops.object.mode_set(mode='EDIT')
        active_bones = [bone.name for bone in active_armature.data.edit_bones]
        bpy.ops.object.mode_set(mode='OBJECT')
        
        bpy.context.view_layer.objects.active = target_armature
        bpy.ops.object.mode_set(mode='EDIT')
        target_bones = [bone.name for bone in target_armature.data.edit_bones]
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 恢复活动对象
        bpy.context.view_layer.objects.active = active_armature
        
        # 查找同名骨骼
        common_bone_names = set(active_bones) & set(target_bones)
        
        if not common_bone_names:
            self.report({'WARNING'}, "未找到同名骨骼，无需添加约束！")
            return {'FINISHED'}
        
        # 切换到姿态模式添加约束
        bpy.ops.object.mode_set(mode='POSE')
        
        added_count = 0
        for bone_name in common_bone_names:
            # 获取活动骨架中的骨骼
            pose_bone = active_armature.pose.bones.get(bone_name)
            if not pose_bone:
                continue
            
            # 检查是否已存在相同的约束
            existing_constraint = None
            for constraint in pose_bone.constraints:
                if (constraint.type == 'COPY_TRANSFORMS' and 
                    constraint.target == target_armature and 
                    constraint.subtarget == bone_name):
                    existing_constraint = constraint
                    break
            
            # 如果约束已存在，更新参数；否则创建新约束
            if existing_constraint:
                constraint = existing_constraint
            else:
                constraint = pose_bone.constraints.new(type='COPY_TRANSFORMS')
                added_count += 1
            
            # 设置约束参数
            constraint.name = f"CopyTransforms_{bone_name}"
            constraint.target = target_armature
            constraint.subtarget = bone_name
            constraint.mix_mode = 'REPLACE'  # 替换模式
            constraint.target_space = 'WORLD'  # 目标空间：世界空间
            constraint.owner_space = 'WORLD'  # 拥有者空间：世界空间
        
        # 反馈结果
        if added_count > 0:
            self.report({'INFO'}, f"成功为 {added_count} 个骨骼添加复制变换约束！")
        else:
            self.report({'INFO'}, f"所有同名骨骼已存在约束，共 {len(common_bone_names)} 个同名骨骼。")
        
        return {'FINISHED'}


class BONE_PT_copy_transforms_panel(bpy.types.Panel):
    """创建插件面板"""
    bl_label = "骨骼复制变换工具"
    bl_idname = "BONE_PT_copy_transforms_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '骨骼工具'
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        
        # 显示选中的骨架信息
        selected_armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        if len(selected_armatures) == 2:
            active_arm = context.active_object if context.active_object in selected_armatures else None
            target_arm = [arm for arm in selected_armatures if arm != active_arm][0] if active_arm else None
            
            layout.label(text="活动骨架: " + (active_arm.name if active_arm else "无"))
            layout.label(text="目标骨架: " + (target_arm.name if target_arm else "无"))
            layout.operator("bone.add_copy_transforms_between_armatures", icon='CONSTRAINT_BONE')
        else:
            layout.label(text="请选中两个不同的骨架物体", icon='INFO')
            layout.operator("bone.add_copy_transforms_between_armatures", icon='CONSTRAINT_BONE').enabled = False


# 注册插件
classes = (
    BONE_OT_copy_transforms_between_armatures,
    BONE_PT_copy_transforms_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()