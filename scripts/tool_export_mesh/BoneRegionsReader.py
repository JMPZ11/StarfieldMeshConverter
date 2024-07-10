import json
import csv
import bpy

import numpy as np


class IDRecorder:
    def __init__(self) -> None:
        self.id = 0

    def get_id(self):
        self.id += 1
        return self.id
    
    def set_id(self, id):
        self.id = id

    def reset_id(self):
        self.id = 0

class ControlBone:
    def __init__(self, bone_name: str) -> None:
        self.bone_name = bone_name
        self.position_maxima = [0, 0, 0]
        self.position_minima = [0, 0, 0]
        self.rotation_maxima = [0, 0, 0]
        self.rotation_minima = [0, 0, 0]
        self.scale_maxima = [0, 0, 0]
        self.scale_minima = [0, 0, 0]

    @staticmethod
    def from_dict(data: dict):
        bone = ControlBone(data['Bone'])
        bone.position_maxima = [data['Maxima']['Position']['x'], data['Maxima']['Position']['y'], data['Maxima']['Position']['z']]
        bone.rotation_maxima = [data['Maxima']['Rotation']['x'], data['Maxima']['Rotation']['y'], data['Maxima']['Rotation']['z']]
        bone.scale_maxima = [data['Maxima']['Scale']['x'], data['Maxima']['Scale']['y'], data['Maxima']['Scale']['z']]
        bone.position_minima = [data['Minima']['Position']['x'], data['Minima']['Position']['y'], data['Minima']['Position']['z']]
        bone.rotation_minima = [data['Minima']['Rotation']['x'], data['Minima']['Rotation']['y'], data['Minima']['Rotation']['z']]
        bone.scale_minima = [data['Minima']['Scale']['x'], data['Minima']['Scale']['y'], data['Minima']['Scale']['z']]
        return bone

    def to_dict(self):
        return {
            'Bone': self.bone_name,
            'Maxima': {
                'Position': {
                    'x': self.position_maxima[0],
                    'y': self.position_maxima[1],
                    'z': self.position_maxima[2]
                },
                'Rotation': {
                    'x': self.rotation_maxima[0],
                    'y': self.rotation_maxima[1],
                    'z': self.rotation_maxima[2]
                },
                'Scale': {
                    'x': self.scale_maxima[0],
                    'y': self.scale_maxima[1],
                    'z': self.scale_maxima[2]
                }
            },
            'Minima': {
                'Position': {
                    'x': self.position_minima[0],
                    'y': self.position_minima[1],
                    'z': self.position_minima[2]
                },
                'Rotation': {
                    'x': self.rotation_minima[0],
                    'y': self.rotation_minima[1],
                    'z': self.rotation_minima[2]
                },
                'Scale': {
                    'x': self.scale_minima[0],
                    'y': self.scale_minima[1],
                    'z': self.scale_minima[2]
                }
            }
        }

    def to_matrix(self)->np.ndarray:
        return np.array([
            self.position_maxima + self.rotation_maxima + self.scale_maxima,
            self.position_minima + self.rotation_minima + self.scale_minima
        ], dtype=np.float32)

class Slider:
    def __init__(self, ID, name: str = "", is_zero_to_one = False) -> None:
        self.id = ID
        self.name = name
        self.is_zero_to_one = is_zero_to_one
        self.bones:dict[str, ControlBone] = {}

    def add_bone(self, bone: ControlBone, overwrite = False):
        # Check if the bone already exists
        if bone.bone_name in self.bones:
            if overwrite:
                self.bones[bone.bone_name] = bone
                return True
            return False
        self.bones[bone.bone_name] = bone
        return True


    @staticmethod
    def new_slider(name: str, is_zero_to_one, id_recorder: IDRecorder):
        return Slider(id_recorder.get_id(), name, is_zero_to_one)

    @staticmethod
    def from_dict(data: dict, id_recorder: IDRecorder):
        slider = Slider(data['ID'], data['Name'], data['ZeroToOne'])
        id_recorder.set_id(data['ID'])
        bones = [ControlBone.from_dict(bone) for bone in data['BonesA']]
        for bone in bones:
            slider.add_bone(bone)
        return slider

    def to_dict(self):
        return {
            'BonesA': [bone.to_dict() for _,bone in self.bones.items()],
            'ID': self.id,
            'Name': self.name,
            'ZeroToOne': self.is_zero_to_one,
        }

    def _dispatch_id(self, id_recorder: IDRecorder):
        self.id = id_recorder.get_id()

class Region:
    def __init__(self, ID, name: str, is_sculpt_region) -> None:
        self.id = ID
        self.name = name
        self.is_sculpt_region = is_sculpt_region
        self.sliders:dict[str, Slider] = {}

    def add_slider(self, slider: Slider, overwrite = False):
        # Check if the slider already exists
        if slider.name in self.sliders:
            if overwrite:
                self.sliders[slider.name] = slider
                return True
            return False
        self.sliders[slider.name] = slider
        return True

    @staticmethod
    def new_region(name: str, is_sculpt_region, id_recorder: IDRecorder):
        return Region(id_recorder.get_id(), name, is_sculpt_region)

    @staticmethod
    def from_dict(data: dict, id_recorder: IDRecorder):
        region = Region(data['ID'], data['Name'], data['SculptRegion'])
        id_recorder.set_id(data['ID'])
        sliders = [Slider.from_dict(slider, id_recorder) for slider in data['SlidersA']]
        for slider in sliders:
            region.add_slider(slider)
        return region

    def to_dict(self):
        return {
            'ID': self.id,
            'Name': self.name,
            'SculptRegion': self.is_sculpt_region,
            'SlidersA': [slider.to_dict() for _, slider in self.sliders.items()]
        }

    def _dispatch_id(self, id_recorder: IDRecorder):
        self.id = id_recorder.get_id()
        for _, slider in self.sliders.items():
            slider._dispatch_id(id_recorder)

    def is_phenotype(self):
        if not self.is_sculpt_region and len(self.sliders) == 1 and "" in self.sliders and self.sliders[""].is_zero_to_one:
            return True
        return False

    def to_matrix(self, bone_names:list[str]) -> np.ndarray:
        if not self.is_phenotype():
            raise ValueError("Region is not a phenotype")
        slider = self.sliders[""]
        matrix = np.zeros((len(bone_names), 9), dtype=np.float32)
        for bone_name, bone in slider.bones.items():
            index = bone_names.index(bone_name)
            matrix[index] = bone.to_matrix()[0]
        return matrix

import functools

class BoneRegions:
    def __init__(self) -> None:
        self.constraints = None
        self.regions:dict[str, Region] = {}
        self.id_recorder = IDRecorder()
        self.bone_names:list[str] = []
        self.face_region_names:list[str] = []
        self.phenotypes:list[str] = []
        self._BR_tensor:np.ndarray = None

    @functools.cached_property 
    def _Pheno_tensor(self):
        '''
            n_bones x n_phenotypes x 9
        '''
        if self.is_emtpy():
            return None
        arr = np.array([self.regions[phenotype].to_matrix(self.bone_names) for phenotype in self.phenotypes])
        
        arr = np.swapaxes(arr, 0, 1)

        return arr

    def import_from_file(self, bone_regions_file: str, bone_regions_mapping_file:str) -> None:
        self.clear()
        data = None
        with open(bone_regions_file, 'r') as file:
            data = json.load(file)

        if data is None:
            return
        
        with open(bone_regions_mapping_file, 'r') as file:
            raw_data = csv.reader(file)

            csvdata = [row for row in raw_data]
            self.face_region_names = csvdata[0][1:]
            self.bone_names = [row[0] for row in csvdata[1:]]
            _BR_matrix = np.array([row[1:] for row in csvdata[1:]], dtype=np.float32) * 0.01
            self._BR_tensor = _BR_matrix[:, :, np.newaxis]

        self.constraints = data['Constraints']
        regions = [Region.from_dict(region, self.id_recorder) for region in data['Regions']]
        for region in regions:
            self.regions[region.name] = region
            if region.is_phenotype():
                self.phenotypes.append(region.name)

    def export_to_file(self, file_path: str) -> None:
        data = {
            'Constraints': self.constraints,
            'Regions': [region.to_dict() for _, region in self.regions.items()]
        }

        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)

    def redispatch_ids(self):
        self.id_recorder.reset_id()
        for _,region in self.regions.items():
            region._dispatch_id(self.id_recorder)
    
    def new_region(self, name: str, is_sculpt_region, overwrite = False):
        # Check if the region already exists
        if name in self.regions:
            if overwrite:
                self.regions[name] = Region.new_region(name, is_sculpt_region, self.id_recorder)
                return self.regions[name]
            return None
        self.regions[name] = Region.new_region(name, is_sculpt_region, self.id_recorder)
        return self.regions[name]
    
    def new_slider(self, region_name, name: str, is_zero_to_one, overwrite = False):
        # Check if the region exists
        if region_name not in self.regions:
            return None
        
        region = self.regions[region_name]
        # Check if the slider already exists
        if name in region.sliders:
            if overwrite:
                region.sliders[name] = Slider.new_slider(name, is_zero_to_one, self.id_recorder)
                return region.sliders[name]
            return None
        region.sliders[name] = Slider.new_slider(name, is_zero_to_one, self.id_recorder)
        return region.sliders[name]
        
    def new_slider_bone(self, region_name, slider_name, bone_name, overwrite = False):
        # Check if the region exists
        if region_name not in self.regions:
            return None
        
        region = self.regions[region_name]
        # Check if the slider exists
        if slider_name not in region.sliders:
            return None
        
        slider = region.sliders[slider_name]
        bone = ControlBone(bone_name)
        slider.add_bone(bone, overwrite)
        return slider.bones[bone_name]
    
    def get_region(self, name: str):
        return self.regions.get(name, None)
    
    def get_slider(self, region_name, name: str):
        region = self.get_region(region_name)
        if region is None:
            return None
        return region.sliders.get(name, None)
    
    def get_slider_bone(self, region_name, slider_name, bone_name):
        slider = self.get_slider(region_name, slider_name)
        if slider is None:
            return None
        return slider.bones.get(bone_name, None)
    
    def remove_region(self, name: str):
        if name in self.regions:
            del self.regions[name]
            return True
        return False

    def remove_slider(self, region_name, name: str):
        region = self.get_region(region_name)
        if region is None:
            return False
        if name in region.sliders:
            del region.sliders[name]
            return True
        return False
    
    def remove_slider_bone(self, region_name, slider_name, bone_name):
        slider = self.get_slider(region_name, slider_name)
        if slider is None:
            return False
        if bone_name in slider.bones:
            del slider.bones[bone_name]
            return True
        return False

    def _forward(self, control_matrix:np.ndarray):
        '''
            control_matrix: n_phenos x n_regions
            return: n_bones x 9
        '''
        return np.sum(np.einsum("ijk,jl->ilk", self._Pheno_tensor, control_matrix) * self._BR_tensor, axis=1)

    def AddPhenotype(self, phenotype_name:str):
        if phenotype_name not in self.regions:
            self.new_region(phenotype_name, False)
            self.new_slider(phenotype_name, "", True)
            self.phenotypes.append(phenotype_name)
        else:
            print(f"Phenotype {phenotype_name} already exists")
        return self.regions[phenotype_name]
    
    def RemovePhenotype(self, phenotype_name:str):
        if phenotype_name in self.phenotypes:
            self.phenotypes.remove(phenotype_name)
        return self.remove_region(phenotype_name)

    def is_valid(self):
        for phenotype in self.phenotypes:
            region = self.regions[phenotype]
            if not region.is_phenotype():
                return False
        return True
    
    def is_emtpy(self):
        return len(self.regions) == 0
    
    def clear(self):
        self.regions.clear()
        self.bone_names.clear()
        self.face_region_names.clear()
        self.phenotypes.clear()
        self._BR_tensor = None
        if hasattr(self, "_Pheno_tensor"):
            del self._Pheno_tensor

    def get_input_shape(self):
        return len(self.phenotypes), len(self.face_region_names)

__bone_regions_data__ = BoneRegions()

if __name__ == "__main__":
    import os
    directory = r'C:\Game\Starfield\MO2\mods\Lupus\meshes\actors\Human\CharacterAssets'
    regions_file = os.path.join(directory, 'LupusRaceFacialBoneRegionsMale.txt')
    mapping_file = os.path.join(directory, 'LupusRaceFacialBoneRegionsMapping.csv')

    bone_regions = BoneRegions()
    bone_regions.import_from_file(regions_file, mapping_file)
    
    control_matrix = np.zeros((len(bone_regions.phenotypes), len(bone_regions.face_region_names)))

    # Set the first row to 1
    control_matrix[0] = 1

    result = bone_regions._forward(control_matrix)

    print(bone_regions.phenotypes[0])
    for bone_name in bone_regions.bone_names:
        print(f"{bone_name}: {result[bone_regions.bone_names.index(bone_name)][3:6]}")