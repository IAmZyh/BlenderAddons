bl_info = {
    "name": "连续骨骼阻尼追踪设置",
    "author": "航于掙",
    "version": (1,6), 
    "blender": (4,0,0),
    "location": "3D视图 > 侧边栏 > 姿态工具",
    "description": "支持多链+头发+自定义关键词骨骼阻尼追踪，可自定义排除/匹配关键词，一键删除阻尼约束，适用于需要物理飘动效果的骨骼",
    "category": "动画",
}

import bpy
import bpy.types
from collections import defaultdict

# 定义全局属性组，存储面板参数
class PoseDampedTrackSettings(bpy.types.PropertyGroup):
    # 通用多链参数
    base_influence: bpy.props.FloatProperty(
        name="最高父级骨骼阻尼追踪影响值",
        description="最顶层骨骼的阻尼追踪影响值",
        min=0.0,
        max=1.0,
        default=0.1,
        step=0.1,
        precision=2
    )
    
    influence_increment: bpy.props.FloatProperty(
        name="影响值逐级增量",
        description="每向下一级骨骼增加的阻尼追踪影响值（达到1后停止，通用于所有骨骼）",
        min=0.0,
        max=1.0,
        default=0.1,
        step=0.1,
        precision=2
    )
    
    prefer_end_as_tail: bpy.props.BoolProperty(
        name="优先识别_end后缀为末端",
        description="若骨骼链中有_end骨骼，自动将其作为链末端（无视选择顺序）",
        default=True
    )
    
    # 通用多链自定义追踪轴
    general_track_axis: bpy.props.EnumProperty(
        name="通用追踪轴",
        description="通用多链骨骼阻尼追踪的轴向",
        items=[
            ('TRACK_Y', 'Y轴', '追踪Y轴'),
            ('TRACK_NEGATIVE_Y', '负Y轴', '追踪负Y轴'),
            ('TRACK_X', 'X轴', '追踪X轴'),
            ('TRACK_NEGATIVE_X', '负X轴', '追踪负X轴'),
            ('TRACK_Z', 'Z轴', '追踪Z轴'),
            ('TRACK_NEGATIVE_Z', '负Z轴', '追踪负Z轴'),
        ],
        default='TRACK_Y'
    )
    
    # 排除关键词配置
    exclude_keywords: bpy.props.StringProperty(
        name="排除关键词",
        description="需要排除的骨骼名称关键词，多个关键词用英文逗号分隔（不区分大小写）",
        default="root",
        maxlen=100
    )
    
    # 头发骨骼专属参数
    hair_influence: bpy.props.FloatProperty(
        name="头发最高父级骨骼阻尼追踪影响值",
        description="头发最顶层骨骼阻尼追踪的影响值",
        min=0.0,
        max=1.0,
        default=0.1,
        step=0.1,
        precision=2
    )
    
    hair_track_axis: bpy.props.EnumProperty(
        name="头发追踪轴",
        description="头发骨骼阻尼追踪的轴向",
        items=[
            ('TRACK_Y', 'Y轴', '追踪Y轴'),
            ('TRACK_NEGATIVE_Y', '负Y轴', '追踪负Y轴'),
            ('TRACK_X', 'X轴', '追踪X轴'),
            ('TRACK_NEGATIVE_X', '负X轴', '追踪负X轴'),
            ('TRACK_Z', 'Z轴', '追踪Z轴'),
            ('TRACK_NEGATIVE_Z', '负Z轴', '追踪负Z轴'),
        ],
        default='TRACK_Y'
    )
    
    # 自定义匹配关键词参数
    custom_match_keywords: bpy.props.StringProperty(
        name="自定义匹配关键词",
        description="需要单独处理的骨骼名称关键词，多个关键词用英文逗号分隔（不区分大小写）",
        default="skirt",
        maxlen=100
    )
    
    custom_influence: bpy.props.FloatProperty(
        name="自定义最高父级骨骼阻尼追踪影响值",
        description="自定义关键词最顶层骨骼阻尼追踪的影响值",
        min=0.0,
        max=1.0,
        default=0.1,
        step=0.1,
        precision=2
    )
    
    custom_track_axis: bpy.props.EnumProperty(
        name="自定义追踪轴",
        description="自定义关键词骨骼阻尼追踪的轴向",
        items=[
            ('TRACK_Y', 'Y轴', '追踪Y轴'),
            ('TRACK_NEGATIVE_Y', '负Y轴', '追踪负Y轴'),
            ('TRACK_X', 'X轴', '追踪X轴'),
            ('TRACK_NEGATIVE_X', '负X轴', '追踪负X轴'),
            ('TRACK_Z', 'Z轴', '追踪Z轴'),
            ('TRACK_NEGATIVE_Z', '负Z轴', '追踪负Z轴'),
        ],
        default='TRACK_Y'
    )

# -------------------------- 通用辅助函数 --------------------------
def get_exclude_keywords_list(context):
    """解析排除关键词为列表（去重、去空格、转小写）"""
    settings = context.scene.pose_damped_track_settings
    # 分割关键词、去空格、转小写、去空值
    keywords = [kw.strip().lower() for kw in settings.exclude_keywords.split(',') if kw.strip()]
    # 去重
    return list(set(keywords))

def get_custom_match_keywords_list(context):
    """解析自定义匹配关键词为列表（去重、去空格、转小写）"""
    settings = context.scene.pose_damped_track_settings
    # 分割关键词、去空格、转小写、去空值
    keywords = [kw.strip().lower() for kw in settings.custom_match_keywords.split(',') if kw.strip()]
    # 去重
    return list(set(keywords))

def is_excluded_bone(bone, context):
    """判断骨骼是否为排除项（匹配自定义关键词）"""
    exclude_keywords = get_exclude_keywords_list(context)
    bone_name_lower = bone.name.lower()
    # 只要包含任意一个排除关键词就返回True
    return any(kw in bone_name_lower for kw in exclude_keywords)

def is_custom_match_bone(bone, context):
    """判断骨骼是否匹配自定义关键词（排除项优先）"""
    if is_excluded_bone(bone, context):
        return False
    custom_keywords = get_custom_match_keywords_list(context)
    bone_name_lower = bone.name.lower()
    # 只要包含任意一个自定义关键词就返回True
    return any(kw in bone_name_lower for kw in custom_keywords)

def analyze_selected_bone_chains(context):
    selected_bones = context.selected_pose_bones.copy()
    if not selected_bones:
        return []
    
    # 过滤排除的骨骼（自定义关键词）
    filtered_bones = [b for b in selected_bones if not is_excluded_bone(b, context)]
    if not filtered_bones:
        return []
    
    # 构建父子映射表
    child_map = defaultdict(list)
    selected_names = {b.name for b in filtered_bones}
    
    for bone in filtered_bones:
        if bone.parent and bone.parent.name in selected_names and not is_excluded_bone(bone.parent, context):
            child_map[bone.parent.name].append(bone)
    
    # 识别末端骨骼
    settings = context.scene.pose_damped_track_settings
    tail_bones = []
    
    if settings.prefer_end_as_tail:
        end_bones = [b for b in filtered_bones if b.name.endswith('_end')]
        if end_bones:
            tail_bones = end_bones
        else:
            for bone in filtered_bones:
                has_selected_child = any(c.name in selected_names and not is_excluded_bone(c, context) for c in child_map[bone.name])
                if not has_selected_child:
                    tail_bones.append(bone)
    else:
        for bone in filtered_bones:
            has_selected_child = any(c.name in selected_names and not is_excluded_bone(c, context) for c in child_map[bone.name])
            if not has_selected_child:
                tail_bones.append(bone)
    
    # 去重
    tail_bones = list({b.name: b for b in tail_bones}.values())
    
    # 构建骨骼链（排除有排除关键词的骨骼）
    bone_chains = []
    processed_names = set()
    
    for tail_bone in tail_bones:
        chain = []
        current_bone = tail_bone
        
        while current_bone and current_bone.name in selected_names and current_bone.name not in processed_names and not is_excluded_bone(current_bone, context):
            chain.append(current_bone)
            processed_names.add(current_bone.name)
            current_bone = current_bone.parent if (current_bone.parent and current_bone.parent.name in selected_names and not is_excluded_bone(current_bone.parent, context)) else None
        
        if len(chain) >= 2:
            chain.reverse()
            bone_chains.append(chain)
    
    return bone_chains

def get_tail_bones_preview(context):
    chains = analyze_selected_bone_chains(context)
    tail_names = [chain[-1].name for chain in chains] if chains else []
    return tail_names

# -------------------------- 统计选中骨骼的阻尼约束数量 --------------------------
def count_damped_track_constraints(selected_bones):
    """统计选中骨骼中的阻尼追踪约束数量"""
    count = 0
    constraint_info = defaultdict(list)
    
    for bone in selected_bones:
        for constraint in bone.constraints:
            if constraint.type == 'DAMPED_TRACK':
                count += 1
                constraint_info[bone.name].append(constraint.name)
    
    return count, constraint_info

# -------------------------- 头发骨骼处理辅助函数 --------------------------
def get_hair_bones_from_selected(selected_bones, context):
    """提取名称含hair/Hair且不含排除关键词的骨骼"""
    hair_bones = []
    for bone in selected_bones:
        if 'hair' in bone.name.lower() and not is_excluded_bone(bone, context):
            hair_bones.append(bone)
    return hair_bones

def build_hair_bone_chain(hair_bone, selected_names, context):
    """为单根头发骨骼构建父子链（排除自定义关键词骨骼）"""
    chain = []
    current_bone = hair_bone
    
    while current_bone and current_bone.name in selected_names and not is_excluded_bone(current_bone, context):
        chain.append(current_bone)
        current_bone = current_bone.parent if (current_bone.parent and current_bone.parent.name in selected_names and not is_excluded_bone(current_bone.parent, context)) else None
    
    # 反向：从根到末端
    if len(chain) >= 2:
        chain.reverse()
    return chain

# -------------------------- 自定义关键词骨骼处理辅助函数 --------------------------
def get_custom_match_bones_from_selected(selected_bones, context):
    """提取匹配自定义关键词且不含排除关键词的骨骼"""
    custom_bones = []
    for bone in selected_bones:
        if is_custom_match_bone(bone, context):
            custom_bones.append(bone)
    return custom_bones

def build_custom_bone_chain(custom_bone, selected_names, context):
    """为单根自定义关键词骨骼构建父子链（排除自定义关键词骨骼）"""
    chain = []
    current_bone = custom_bone
    
    while current_bone and current_bone.name in selected_names and not is_excluded_bone(current_bone, context):
        chain.append(current_bone)
        current_bone = current_bone.parent if (current_bone.parent and current_bone.parent.name in selected_names and not is_excluded_bone(current_bone.parent, context)) else None
    
    # 反向：从根到末端
    if len(chain) >= 2:
        chain.reverse()
    return chain

# -------------------------- 通用多链操作符 --------------------------
class POSE_OT_add_multi_chain_damped_track(bpy.types.Operator):
    """为任意多条骨骼链批量添加层级阻尼追踪约束（排除自定义关键词）"""
    bl_idname = "pose.add_multi_chain_damped_track"
    bl_label = "添加多链阻尼追踪约束"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE' or not context.selected_pose_bones:
            return False
        # 过滤后至少有2个骨骼才可用
        filtered_bones = [b for b in context.selected_pose_bones if not is_excluded_bone(b, context)]
        return len(filtered_bones) >= 2
    
    def execute(self, context):
        settings = context.scene.pose_damped_track_settings
        base_influence = settings.base_influence
        influence_increment = settings.influence_increment
        general_track_axis = settings.general_track_axis  # 获取通用追踪轴
        
        bone_chains = analyze_selected_bone_chains(context)
        if not bone_chains:
            self.report({'WARNING'}, f"未检测到有效骨骼链（排除关键词[{settings.exclude_keywords}]后不足2个骨骼）")
            return {'CANCELLED'}
        
        # 统计排除的骨骼
        excluded_bones = [b.name for b in context.selected_pose_bones if is_excluded_bone(b, context)]
        exclude_keywords = get_exclude_keywords_list(context)
        excluded_info = f"（排除{len(excluded_bones)}个含[{','.join(exclude_keywords)}]的骨骼：{', '.join(excluded_bones[:3])}...）" if excluded_bones else ""
        
        total_processed_chains = 0
        total_processed_bones = 0
        chain_info = []
        
        for chain in bone_chains:
            chain_tail = chain[-1].name
            chain_influence_info = []
            
            for i in range(len(chain) - 1):
                source_bone = chain[i]
                target_bone = chain[i + 1]
                
                current_influence = min(base_influence + (influence_increment * i), 1.0)
                chain_influence_info.append(f"{source_bone.name}: {current_influence:.2f}")
                
                # 移除旧约束
                for constraint in source_bone.constraints:
                    if constraint.type == 'DAMPED_TRACK':
                        source_bone.constraints.remove(constraint)
                
                # 创建新约束（使用自定义追踪轴，固定head_tail=0.0）
                damped_track = source_bone.constraints.new(type='DAMPED_TRACK')
                damped_track.target = context.active_object
                damped_track.subtarget = target_bone.name
                damped_track.track_axis = general_track_axis  # 替换为自定义通用追踪轴
                damped_track.head_tail = 0.0  # 固定为0.0
                damped_track.influence = current_influence
                
                total_processed_bones += 1
            
            chain_info.append(f"链[{chain_tail}]: {' | '.join(chain_influence_info)}")
            total_processed_chains += 1
        
        self.report({'INFO'}, 
                    f"成功处理{total_processed_chains}条骨骼链，共{total_processed_bones}个骨骼{excluded_info}\n"
                    f"通用追踪轴: {general_track_axis.replace('TRACK_', '').replace('_', ' ')}\n"
                    f"详情: {' | '.join(chain_info)}")
        return {'FINISHED'}

# -------------------------- 头发骨骼专属操作符 --------------------------
class POSE_OT_add_hair_bone_damped_track(bpy.types.Operator):
    """为名称含hair/Hair的骨骼添加阻尼追踪约束（排除自定义关键词）"""
    bl_idname = "pose.add_hair_bone_damped_track"
    bl_label = "添加头发骨骼阻尼追踪约束"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE' or not context.selected_pose_bones:
            return False
        hair_bones = get_hair_bones_from_selected(context.selected_pose_bones, context)
        return len(hair_bones) >= 2
    
    def execute(self, context):
        settings = context.scene.pose_damped_track_settings
        hair_influence = settings.hair_influence
        hair_track_axis = settings.hair_track_axis
        
        # 获取选中的头发骨骼（排除自定义关键词）
        selected_bones = context.selected_pose_bones.copy()
        selected_names = {b.name for b in selected_bones}
        hair_bones = get_hair_bones_from_selected(selected_bones, context)
        
        if not hair_bones:
            exclude_keywords = get_exclude_keywords_list(context)
            self.report({'WARNING'}, f"未检测到名称含hair/Hair且不含[{','.join(exclude_keywords)}]的骨骼")
            return {'CANCELLED'}
        
        # 统计排除的头发骨骼
        excluded_hair_bones = [b.name for b in selected_bones if 'hair' in b.name.lower() and is_excluded_bone(b, context)]
        exclude_keywords = get_exclude_keywords_list(context)
        excluded_info = f"（排除{len(excluded_hair_bones)}个头发骨骼（含[{','.join(exclude_keywords)}]）：{', '.join(excluded_hair_bones[:3])}...）" if excluded_hair_bones else ""
        
        # 构建头发骨骼链
        hair_chains = []
        processed_names = set()
        
        for hair_bone in hair_bones:
            if hair_bone.name in processed_names:
                continue
            # 构建单根头发的父子链（排除自定义关键词）
            hair_chain = build_hair_bone_chain(hair_bone, selected_names, context)
            if len(hair_chain) >= 2:
                hair_chains.append(hair_chain)
                # 标记已处理
                for b in hair_chain:
                    processed_names.add(b.name)
        
        if not hair_chains:
            self.report({'WARNING'}, f"未检测到有效头发骨骼链（排除关键词[{settings.exclude_keywords}]后不足2个骨骼）")
            return {'CANCELLED'}
        
        # 为头发链添加约束
        total_processed_chains = 0
        total_processed_bones = 0
        hair_info = []
        
        for chain in hair_chains:
            chain_tail = chain[-1].name
            chain_influence_info = []
            
            for i in range(len(chain) - 1):
                source_bone = chain[i]
                target_bone = chain[i + 1]
                
                # 头发骨骼使用固定影响值+增量（不超过1）
                current_influence = min(hair_influence + (settings.influence_increment * i), 1.0)
                chain_influence_info.append(f"{source_bone.name}: {current_influence:.2f}")
                
                # 移除旧约束
                for constraint in source_bone.constraints:
                    if constraint.type == 'DAMPED_TRACK':
                        source_bone.constraints.remove(constraint)
                
                # 创建头发专属约束（固定head_tail=0.0）
                damped_track = source_bone.constraints.new(type='DAMPED_TRACK')
                damped_track.target = context.active_object
                damped_track.subtarget = target_bone.name
                damped_track.track_axis = hair_track_axis  # 头发专属追踪轴
                damped_track.head_tail = 0.0  # 固定为0.0
                damped_track.influence = current_influence
                
                total_processed_bones += 1
            
            hair_info.append(f"头发链[{chain_tail}]: {' | '.join(chain_influence_info)}")
            total_processed_chains += 1
        
        self.report({'INFO'}, 
                    f"成功处理{total_processed_chains}条头发骨骼链，共{total_processed_bones}个骨骼{excluded_info}\n"
                    f"详情: {' | '.join(hair_info)}")
        return {'FINISHED'}

# -------------------------- 自定义关键词骨骼专属操作符 --------------------------
class POSE_OT_add_custom_bone_damped_track(bpy.types.Operator):
    """为匹配自定义关键词的骨骼添加阻尼追踪约束（排除自定义关键词）"""
    bl_idname = "pose.add_custom_bone_damped_track"
    bl_label = "添加自定义关键词骨骼阻尼追踪约束"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if context.mode != 'POSE' or not context.selected_pose_bones:
            return False
        custom_bones = get_custom_match_bones_from_selected(context.selected_pose_bones, context)
        return len(custom_bones) >= 2
    
    def execute(self, context):
        settings = context.scene.pose_damped_track_settings
        custom_influence = settings.custom_influence
        custom_track_axis = settings.custom_track_axis
        
        # 获取选中的自定义关键词骨骼（排除自定义关键词）
        selected_bones = context.selected_pose_bones.copy()
        selected_names = {b.name for b in selected_bones}
        custom_bones = get_custom_match_bones_from_selected(selected_bones, context)
        
        if not custom_bones:
            custom_keywords = get_custom_match_keywords_list(context)
            exclude_keywords = get_exclude_keywords_list(context)
            self.report({'WARNING'}, f"未检测到匹配[{','.join(custom_keywords)}]且不含[{','.join(exclude_keywords)}]的骨骼")
            return {'CANCELLED'}
        
        # 统计排除的自定义骨骼
        excluded_custom_bones = [b.name for b in selected_bones if is_custom_match_bone(b, context) and is_excluded_bone(b, context)]
        exclude_keywords = get_exclude_keywords_list(context)
        excluded_info = f"（排除{len(excluded_custom_bones)}个匹配关键词但含[{','.join(exclude_keywords)}]的骨骼：{', '.join(excluded_custom_bones[:3])}...）" if excluded_custom_bones else ""
        
        # 构建自定义骨骼链
        custom_chains = []
        processed_names = set()
        
        for custom_bone in custom_bones:
            if custom_bone.name in processed_names:
                continue
            # 构建单根自定义骨骼的父子链（排除自定义关键词）
            custom_chain = build_custom_bone_chain(custom_bone, selected_names, context)
            if len(custom_chain) >= 2:
                custom_chains.append(custom_chain)
                # 标记已处理
                for b in custom_chain:
                    processed_names.add(b.name)
        
        if not custom_chains:
            custom_keywords = get_custom_match_keywords_list(context)
            self.report({'WARNING'}, f"未检测到有效自定义骨骼链（匹配[{','.join(custom_keywords)}]且排除关键词后不足2个骨骼）")
            return {'CANCELLED'}
        
        # 为自定义链添加约束
        total_processed_chains = 0
        total_processed_bones = 0
        custom_info = []
        
        for chain in custom_chains:
            chain_tail = chain[-1].name
            chain_influence_info = []
            
            for i in range(len(chain) - 1):
                source_bone = chain[i]
                target_bone = chain[i + 1]
                
                # 自定义骨骼使用固定影响值+增量（不超过1）
                current_influence = min(custom_influence + (settings.influence_increment * i), 1.0)
                chain_influence_info.append(f"{source_bone.name}: {current_influence:.2f}")
                
                # 移除旧约束
                for constraint in source_bone.constraints:
                    if constraint.type == 'DAMPED_TRACK':
                        source_bone.constraints.remove(constraint)
                
                # 创建自定义专属约束（固定head_tail=0.0）
                damped_track = source_bone.constraints.new(type='DAMPED_TRACK')
                damped_track.target = context.active_object
                damped_track.subtarget = target_bone.name
                damped_track.track_axis = custom_track_axis  # 自定义追踪轴
                damped_track.head_tail = 0.0  # 固定为0.0
                damped_track.influence = current_influence
                
                total_processed_bones += 1
            
            custom_info.append(f"自定义链[{chain_tail}]: {' | '.join(chain_influence_info)}")
            total_processed_chains += 1
        
        self.report({'INFO'}, 
                    f"成功处理{total_processed_chains}条自定义骨骼链，共{total_processed_bones}个骨骼{excluded_info}\n"
                    f"详情: {' | '.join(custom_info)}")
        return {'FINISHED'}

# -------------------------- 新增：删除阻尼追踪约束操作符 --------------------------
class POSE_OT_remove_selected_damped_track(bpy.types.Operator):
    """一键删除选中骨骼中所有的阻尼追踪约束"""
    bl_idname = "pose.remove_selected_damped_track"
    bl_label = "删除选中骨骼阻尼追踪约束"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # 仅在姿态模式且有选中骨骼时可用
        return context.mode == 'POSE' and context.selected_pose_bones
    
    def execute(self, context):
        selected_bones = context.selected_pose_bones.copy()
        if not selected_bones:
            self.report({'WARNING'}, "未选中任何骨骼")
            return {'CANCELLED'}
        
        # 统计并删除阻尼追踪约束
        total_removed = 0
        removed_info = defaultdict(list)
        
        for bone in selected_bones:
            # 反向遍历约束列表（避免删除时索引错乱）
            for constraint in reversed(bone.constraints):
                if constraint.type == 'DAMPED_TRACK':
                    # 记录删除信息
                    removed_info[bone.name].append(constraint.name)
                    # 删除约束
                    bone.constraints.remove(constraint)
                    total_removed += 1
        
        if total_removed == 0:
            self.report({'INFO'}, "选中的骨骼中未找到任何阻尼追踪约束")
            return {'FINISHED'}
        
        # 构建提示信息
        info_lines = []
        for bone_name, constraints in removed_info.items():
            info_lines.append(f"{bone_name}: {len(constraints)}个约束")
        
        self.report({'INFO'}, 
                    f"成功删除{total_removed}个阻尼追踪约束\n"
                    f"详情: {'; '.join(info_lines)}")
        return {'FINISHED'}

# -------------------------- 面板 --------------------------
class VIEW3D_PT_multi_chain_damped_track(bpy.types.Panel):
    """通用+头发+自定义关键词骨骼阻尼追踪工具面板"""
    bl_label = "骨骼阻尼追踪工具（多类型支持）"
    bl_idname = "VIEW3D_PT_multi_chain_damped_track"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '姿态工具'
    bl_context = "posemode"
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.pose_damped_track_settings
        selected_bones = context.selected_pose_bones
        
        # 1. 排除关键词配置区
        box = layout.box()
        box.label(text="排除骨骼配置", icon='FILTER')
        box.prop(settings, "exclude_keywords")
        # 显示解析后的关键词（辅助用户确认）
        exclude_keywords = get_exclude_keywords_list(context)
        if exclude_keywords:
            box.label(text=f"当前生效排除关键词（小写）：{', '.join(exclude_keywords)}", icon='INFO')
        else:
            box.label(text="未配置排除关键词（所有骨骼都将处理）", icon='WARNING')
        
        # 2. 通用多链参数区
        box = layout.box()
        box.label(text="通用多链约束参数", icon='BONE_DATA')
        box.prop(settings, "base_influence")
        box.prop(settings, "influence_increment")
        box.prop(settings, "prefer_end_as_tail")
        box.prop(settings, "general_track_axis")  # 通用追踪轴选项
        
        # 3. 头发骨骼专属参数区
        box = layout.box()
        box.label(text="头发骨骼专属参数", icon='CURVES')
        box.prop(settings, "hair_influence")
        box.prop(settings, "hair_track_axis")
        
        # 4. 自定义关键词骨骼专属参数区
        box = layout.box()
        box.label(text="自定义关键词骨骼专属参数", icon='TEXT')
        box.prop(settings, "custom_match_keywords")
        # 显示解析后的自定义关键词（辅助用户确认）
        custom_keywords = get_custom_match_keywords_list(context)
        if custom_keywords:
            box.label(text=f"当前生效匹配关键词（小写）：{', '.join(custom_keywords)}", icon='INFO')
        else:
            box.label(text="未配置匹配关键词（无骨骼会被匹配）", icon='WARNING')
        box.prop(settings, "custom_influence")
        box.prop(settings, "custom_track_axis")
        
        # 5. 操作按钮区
        layout.separator()
        
        # 删除约束按钮
        col = layout.column(align=True)
        delete_row = col.row(align=True)
        delete_row.scale_y = 1.2  # 放大按钮
        delete_op = delete_row.operator("pose.remove_selected_damped_track", 
                                        icon='TRASH', 
                                        text="删除选中骨骼所有阻尼追踪约束",
                                        emboss=True)
        # 设置按钮样式（红色）
        delete_row.alert = True
        
        # 添加约束按钮组
        col.separator()
        col.label(text="添加约束工具：", icon='ADD')
        add_col = col.column(align=True)
        # 通用多链按钮
        add_col.operator("pose.add_multi_chain_damped_track", 
                         icon='CONSTRAINT', 
                         text="批量添加多链阻尼约束",
                         emboss=True)
        # 头发骨骼专属按钮
        add_col.operator("pose.add_hair_bone_damped_track", 
                         icon='CURVES', 
                         text="一键添加头发骨骼阻尼约束",
                         emboss=True)
        # 自定义关键词骨骼专属按钮
        add_col.operator("pose.add_custom_bone_damped_track", 
                         icon='TEXT', 
                         text="一键添加自定义关键词骨骼阻尼约束",
                         emboss=True)

# 6. 选中骨骼分析区
        box = layout.box()
        box.label(text="选中骨骼分析（按关键词过滤）", icon='INFO')
        if selected_bones:
            total_count = len(selected_bones)
            # 过滤排除的骨骼
            excluded_count = len([b for b in selected_bones if is_excluded_bone(b, context)])
            filtered_count = total_count - excluded_count
            # 头发骨骼统计
            hair_bones = get_hair_bones_from_selected(selected_bones, context)
            hair_count = len(hair_bones)
            # 自定义关键词骨骼统计
            custom_bones = get_custom_match_bones_from_selected(selected_bones, context)
            custom_count = len(custom_bones)
            # 通用链统计
            tail_names = get_tail_bones_preview(context)
            chain_count = len(tail_names)
            # 统计阻尼约束数量
            damped_count, damped_info = count_damped_track_constraints(selected_bones)
            
            box.label(text=f"总选中骨骼: {total_count}")
            box.label(text=f"排除关键词骨骼: {excluded_count}")
            box.label(text=f"有效骨骼数: {filtered_count}")
            box.label(text=f"有效头发骨骼: {hair_count}")
            box.label(text=f"有效自定义关键词骨骼: {custom_count}")
            box.label(text=f"有效通用链: {chain_count} 条")
            # 显示阻尼约束数量
            box.label(text=f"当前阻尼追踪约束数: {damped_count}", 
                      icon='CONSTRAINT' if damped_count > 0 else 'INFO')
            
            # 排除的骨骼预览
            if excluded_count > 0:
                box.label(text="已排除的骨骼：", icon='X')
                excluded_names = [b.name for b in selected_bones if is_excluded_bone(b, context)][:3]
                box.label(text=f"  {', '.join(excluded_names)}...")
            
            # 头发骨骼预览
            if hair_count > 0:
                box.label(text="有效头发骨骼：", icon='CHECKMARK')
                for i, bone in enumerate(hair_bones[:5]):  # 最多显示5个
                    box.label(text=f"  {i+1}. {bone.name}")
                if hair_count > 5:
                    box.label(text=f"  ... 共{hair_count}个头发骨骼")
            
            # 自定义关键词骨骼预览
            if custom_count > 0:
                box.label(text="有效自定义关键词骨骼：", icon='CHECKMARK')
                for i, bone in enumerate(custom_bones[:5]):  # 最多显示5个
                    box.label(text=f"  {i+1}. {bone.name}")
                if custom_count > 5:
                    box.label(text=f"  ... 共{custom_count}个自定义骨骼")
            
            # 通用链预览
            if chain_count > 0:
                box.label(text="有效通用骨骼链：", icon='CHECKMARK')
                for i, tail_name in enumerate(tail_names[:3]):  # 最多显示3条链
                    is_end = tail_name.endswith('_end')
                    tag = "(_end)" if is_end else ""
                    box.label(text=f"  链{i+1}末端: {tail_name}{tag}")
            
            # 显示阻尼约束信息
            if damped_count > 0:
                box.label(text=" 检测到阻尼追踪约束：", icon='CONSTRAINT')
                display_count = 0
                for bone_name, constraints in damped_info.items():
                    if display_count >= 3:  # 最多显示3个骨骼的约束信息
                        box.label(text=f"  ... 还有{sum(len(v) for k, v in damped_info.items()) - display_count}个约束")
                        break
                    box.label(text=f"  {bone_name}: {len(constraints)}个")
                    display_count += len(constraints)
        else:
            box.label(text="未选中任何骨骼", icon='INFO')
        
        # 7. 使用说明
        box = layout.box()
        box.label(text="使用说明", icon='HELP')
        box.label(text="排除/自定义关键词配置：")
        box.label(text="  1. 多个关键词用英文逗号分隔（如：root,base,core）")
        box.label(text="  2. 匹配不区分大小写（root ≡ Root ≡ ROOT）")
        box.label(text="  3. 清空输入框则不排除或自定义指定任何骨骼")
        box.label(text="  阻尼约束值设定：")
        box.label(text="  1. 选中任意骨骼链，调整参数后点击按钮")
        box.label(text="  2.头发/自定义约束：选中对应关键词骨骼链，调整参数后点击按钮")

# -------------------------- 注册/反注册 --------------------------
classes = (
    PoseDampedTrackSettings,
    POSE_OT_add_multi_chain_damped_track,
    POSE_OT_add_hair_bone_damped_track,
    POSE_OT_add_custom_bone_damped_track,
    POSE_OT_remove_selected_damped_track,  
    VIEW3D_PT_multi_chain_damped_track,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pose_damped_track_settings = bpy.props.PointerProperty(
        type=PoseDampedTrackSettings
    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pose_damped_track_settings

if __name__ == "__main__":
    register()