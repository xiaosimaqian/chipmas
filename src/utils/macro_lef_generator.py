"""
Macro LEF Generator

This module generates abstract LEF (Library Exchange Format) files for placed partitions.
These LEF files treat each partition as a macro block that can be used in top-level placement.

Key Features:
- Extracts partition boundary information from DEF files
- Generates PIN definitions based on boundary nets
- Creates OBSTRUCTION layers to represent partition area
- Produces standard LEF format compatible with OpenROAD
"""

from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


class MacroLEFGenerator:
    """
    Generates abstract LEF files for physical partitions
    
    A macro LEF contains:
    1. MACRO header (partition name, size)
    2. PIN definitions (boundary connections)
    3. OBS (Obstruction) layers
    4. CLASS (BLOCK or ENDCAP)
    """
    
    def __init__(self, tech_lef_path: Path):
        """
        Initialize the generator
        
        Args:
            tech_lef_path: Path to technology LEF file (for layer info)
        """
        self.tech_lef_path = tech_lef_path
        self.layer_info = self._parse_tech_lef()
        
    def _parse_tech_lef(self) -> Dict:
        """
        Parse technology LEF to extract layer information
        
        Returns:
            Dictionary containing layer names and properties
        """
        if not self.tech_lef_path.exists():
            logger.warning(f"Technology LEF not found: {self.tech_lef_path}")
            # Return default layers for ISPD 2015 designs
            return {
                'routing_layers': ['metal1', 'metal2', 'metal3', 'metal4', 
                                   'metal5', 'metal6', 'metal7', 'metal8'],
                'default_pin_layer': 'metal3',
                'default_obs_layer': 'metal1'
            }
        
        layers = {
            'routing_layers': [],
            'default_pin_layer': 'metal3',
            'default_obs_layer': 'metal1'
        }
        
        try:
            with open(self.tech_lef_path, 'r') as f:
                content = f.read()
                
            # Extract routing layers
            layer_pattern = r'LAYER\s+(\w+)\s+TYPE\s+ROUTING'
            for match in re.finditer(layer_pattern, content):
                layers['routing_layers'].append(match.group(1))
                
        except Exception as e:
            logger.error(f"Error parsing tech LEF: {e}")
            
        return layers
    
    def _parse_def_boundary(self, def_path: Path) -> Dict:
        """
        Parse DEF file to extract partition boundary information
        
        Args:
            def_path: Path to partition DEF file
            
        Returns:
            Dictionary with:
            - bbox: (x_min, y_min, x_max, y_max)
            - pins: List of pin info {name, layer, location}
            - dbu: Design units per micron
        """
        if not def_path.exists():
            raise FileNotFoundError(f"DEF file not found: {def_path}")
        
        result = {
            'bbox': None,
            'pins': [],
            'dbu': 1000,  # default
            'design_name': None
        }
        
        with open(def_path, 'r') as f:
            content = f.read()
        
        # Extract design name
        match = re.search(r'DESIGN\s+(\S+)', content)
        if match:
            result['design_name'] = match.group(1)
        
        # Extract DBU
        match = re.search(r'UNITS DISTANCE MICRONS\s+(\d+)', content)
        if match:
            result['dbu'] = int(match.group(1))
        
        # Extract die area
        match = re.search(r'DIEAREA\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)', content)
        if match:
            x1, y1 = int(match.group(1)), int(match.group(2))
            x2, y2 = int(match.group(3)), int(match.group(4))
            result['bbox'] = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        
        # Extract pins section
        pins_match = re.search(r'PINS\s+(\d+)\s*;(.*?)END PINS', content, re.DOTALL)
        if pins_match:
            num_pins = int(pins_match.group(1))
            pins_section = pins_match.group(2)
            
            # Parse individual pins
            # Pattern: - pin_name + NET net_name + DIRECTION dir + LAYER layer ( x1 y1 ) ( x2 y2 ) ;
            pin_pattern = r'-\s+(\S+)\s+((?:\+\s+\S+[^;]*)+);'
            
            for pin_match in re.finditer(pin_pattern, pins_section):
                pin_name = pin_match.group(1)
                pin_attrs = pin_match.group(2)
                
                pin_info = {
                    'name': pin_name,
                    'net': None,
                    'direction': 'INPUT',  # default
                    'layer': self.layer_info['default_pin_layer'],
                    'location': None,
                    'bbox': None,
                    'shape': 'RECT'
                }
                
                # Extract NET
                net_match = re.search(r'\+\s+NET\s+(\S+)', pin_attrs)
                if net_match:
                    pin_info['net'] = net_match.group(1)
                
                # Extract DIRECTION
                dir_match = re.search(r'\+\s+DIRECTION\s+(\S+)', pin_attrs)
                if dir_match:
                    pin_info['direction'] = dir_match.group(1)
                
                # Extract LAYER and coordinates
                layer_match = re.search(r'\+\s+LAYER\s+(\S+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)', pin_attrs)
                if layer_match:
                    pin_info['layer'] = layer_match.group(1)
                    x1, y1 = int(layer_match.group(2)), int(layer_match.group(3))
                    x2, y2 = int(layer_match.group(4)), int(layer_match.group(5))
                    pin_info['bbox'] = (x1, y1, x2, y2)
                    pin_info['location'] = ((x1 + x2) // 2, (y1 + y2) // 2)
                
                result['pins'].append(pin_info)
        
        return result
    
    def _format_coordinates(self, coord: int, dbu: int) -> float:
        """Convert DEF coordinates to LEF microns"""
        return coord / dbu
    
    def generate_macro_lef(
        self,
        partition_name: str,
        def_path: Path,
        output_path: Path,
        class_type: str = 'BLOCK'
    ) -> Path:
        """
        Generate a macro LEF file for a partition
        
        Args:
            partition_name: Name of the partition (will be used as MACRO name)
            def_path: Path to partition DEF file
            output_path: Path to output LEF file
            class_type: LEF CLASS type (BLOCK, CORE, PAD, etc.)
            
        Returns:
            Path to generated LEF file
        """
        logger.info(f"Generating macro LEF for partition: {partition_name}")
        
        # Parse DEF to get boundary info
        def_info = self._parse_def_boundary(def_path)
        
        if def_info['bbox'] is None:
            raise ValueError(f"Could not extract DIEAREA from {def_path}")
        
        # Calculate macro size
        x_min, y_min, x_max, y_max = def_info['bbox']
        dbu = def_info['dbu']
        
        width = self._format_coordinates(x_max - x_min, dbu)
        height = self._format_coordinates(y_max - y_min, dbu)
        
        # Generate LEF content
        lef_lines = []
        
        # Header
        lef_lines.append(f"VERSION 5.8 ;")
        lef_lines.append(f"BUSBITCHARS \"[]\" ;")
        lef_lines.append(f"DIVIDERCHAR \"/\" ;")
        lef_lines.append(f"")
        
        # Macro definition
        lef_lines.append(f"MACRO {partition_name}")
        lef_lines.append(f"  CLASS {class_type} ;")
        lef_lines.append(f"  FOREIGN {partition_name} 0.0 0.0 ;")
        lef_lines.append(f"  ORIGIN 0.0 0.0 ;")
        lef_lines.append(f"  SIZE {width:.3f} BY {height:.3f} ;")
        lef_lines.append(f"  SYMMETRY X Y ;")
        lef_lines.append(f"")
        
        # Pin definitions
        for pin in def_info['pins']:
            lef_lines.append(f"  PIN {pin['name']}")
            lef_lines.append(f"    DIRECTION {pin['direction']} ;")
            lef_lines.append(f"    USE SIGNAL ;")
            
            if pin['location']:
                # Pin location relative to partition origin
                pin_x = self._format_coordinates(pin['bbox'][0] - x_min, dbu)
                pin_y = self._format_coordinates(pin['bbox'][1] - y_min, dbu)
                pin_x2 = self._format_coordinates(pin['bbox'][2] - x_min, dbu)
                pin_y2 = self._format_coordinates(pin['bbox'][3] - y_min, dbu)
                
                lef_lines.append(f"    PORT")
                lef_lines.append(f"      LAYER {pin['layer']} ;")
                lef_lines.append(f"        RECT {pin_x:.3f} {pin_y:.3f} {pin_x2:.3f} {pin_y2:.3f} ;")
                lef_lines.append(f"    END")
            
            lef_lines.append(f"  END {pin['name']}")
            lef_lines.append(f"")
        
        # Obstruction layer (blocks the entire partition area)
        lef_lines.append(f"  OBS")
        for layer in self.layer_info['routing_layers'][:4]:  # Use first 4 metal layers
            lef_lines.append(f"    LAYER {layer} ;")
            lef_lines.append(f"      RECT 0.0 0.0 {width:.3f} {height:.3f} ;")
        lef_lines.append(f"  END")
        lef_lines.append(f"")
        
        # End macro
        lef_lines.append(f"END {partition_name}")
        lef_lines.append(f"")
        lef_lines.append(f"END LIBRARY")
        lef_lines.append(f"")
        
        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write('\n'.join(lef_lines))
        
        logger.info(f"Macro LEF generated: {output_path}")
        logger.info(f"  Size: {width:.3f} x {height:.3f} microns")
        logger.info(f"  Pins: {len(def_info['pins'])}")
        
        return output_path
    
    def generate_batch_macro_lefs(
        self,
        partitions: Dict[int, Path],
        output_dir: Path
    ) -> Dict[int, Path]:
        """
        Generate macro LEF files for multiple partitions
        
        Args:
            partitions: Dictionary mapping partition_id to DEF path
            output_dir: Directory for output LEF files
            
        Returns:
            Dictionary mapping partition_id to LEF path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        lef_paths = {}
        for partition_id, def_path in partitions.items():
            partition_name = f"partition_{partition_id}"
            lef_path = output_dir / f"{partition_name}.lef"
            
            try:
                self.generate_macro_lef(
                    partition_name=partition_name,
                    def_path=def_path,
                    output_path=lef_path
                )
                lef_paths[partition_id] = lef_path
            except Exception as e:
                logger.error(f"Failed to generate LEF for partition {partition_id}: {e}")
        
        return lef_paths


def generate_partition_macro_lef(
    partition_name: str,
    def_path: Path,
    tech_lef_path: Path,
    output_path: Path
) -> Path:
    """
    Convenience function to generate a single macro LEF
    
    Args:
        partition_name: Name of the partition
        def_path: Path to partition DEF file
        tech_lef_path: Path to technology LEF file
        output_path: Path to output LEF file
        
    Returns:
        Path to generated LEF file
    """
    generator = MacroLEFGenerator(tech_lef_path)
    return generator.generate_macro_lef(partition_name, def_path, output_path)


if __name__ == '__main__':
    # Test example
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 4:
        print("Usage: python macro_lef_generator.py <partition_name> <def_path> <tech_lef_path> [output_path]")
        sys.exit(1)
    
    partition_name = sys.argv[1]
    def_path = Path(sys.argv[2])
    tech_lef_path = Path(sys.argv[3])
    output_path = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(f"{partition_name}.lef")
    
    generate_partition_macro_lef(partition_name, def_path, tech_lef_path, output_path)

