"""
Unit tests for Macro LEF Generator
"""

from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.macro_lef_generator import MacroLEFGenerator, generate_partition_macro_lef


def create_test_def(def_path: Path):
    """Create a simple test DEF file"""
    def_content = """VERSION 5.8 ;
DIVIDERCHAR "/" ;
BUSBITCHARS "[]" ;
DESIGN partition_0 ;
UNITS DISTANCE MICRONS 1000 ;

DIEAREA ( 0 0 ) ( 10000 10000 ) ;

PINS 4 ;
- pin_0 + NET net_0 + DIRECTION INPUT
  + LAYER metal3 ( 0 5000 ) ( 100 5100 ) ;
- pin_1 + NET net_1 + DIRECTION OUTPUT
  + LAYER metal3 ( 10000 5000 ) ( 10100 5100 ) ;
- pin_2 + NET net_2 + DIRECTION INPUT
  + LAYER metal3 ( 5000 0 ) ( 5100 100 ) ;
- pin_3 + NET net_3 + DIRECTION OUTPUT
  + LAYER metal3 ( 5000 10000 ) ( 5100 10100 ) ;
END PINS

COMPONENTS 10 ;
- inst_0 cell_type + PLACED ( 1000 1000 ) N ;
- inst_1 cell_type + PLACED ( 2000 2000 ) N ;
- inst_2 cell_type + PLACED ( 3000 3000 ) N ;
- inst_3 cell_type + PLACED ( 4000 4000 ) N ;
- inst_4 cell_type + PLACED ( 5000 5000 ) N ;
- inst_5 cell_type + PLACED ( 6000 6000 ) N ;
- inst_6 cell_type + PLACED ( 7000 7000 ) N ;
- inst_7 cell_type + PLACED ( 8000 8000 ) N ;
- inst_8 cell_type + PLACED ( 9000 9000 ) N ;
- inst_9 cell_type + PLACED ( 1000 9000 ) N ;
END COMPONENTS

NETS 4 ;
- net_0 ( pin_0 ) ( inst_0 A ) ;
- net_1 ( inst_9 Y ) ( pin_1 ) ;
- net_2 ( pin_2 ) ( inst_5 B ) ;
- net_3 ( inst_5 Y ) ( pin_3 ) ;
END NETS

END DESIGN
"""
    def_path.parent.mkdir(parents=True, exist_ok=True)
    with open(def_path, 'w') as f:
        f.write(def_content)


def create_test_tech_lef(lef_path: Path):
    """Create a simple test technology LEF file"""
    lef_content = """VERSION 5.8 ;
BUSBITCHARS "[]" ;
DIVIDERCHAR "/" ;

LAYER metal1
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 0.2 ;
  WIDTH 0.1 ;
END metal1

LAYER metal2
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  PITCH 0.2 ;
  WIDTH 0.1 ;
END metal2

LAYER metal3
  TYPE ROUTING ;
  DIRECTION HORIZONTAL ;
  PITCH 0.4 ;
  WIDTH 0.2 ;
END metal3

LAYER metal4
  TYPE ROUTING ;
  DIRECTION VERTICAL ;
  PITCH 0.4 ;
  WIDTH 0.2 ;
END metal4

END LIBRARY
"""
    lef_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lef_path, 'w') as f:
        f.write(lef_content)


def test_macro_lef_generator_init():
    """Test MacroLEFGenerator initialization"""
    print("\n" + "="*80)
    print("TEST: MacroLEFGenerator Initialization")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        tech_lef = tmpdir / "tech.lef"
        create_test_tech_lef(tech_lef)
        
        generator = MacroLEFGenerator(tech_lef)
        
        assert generator.tech_lef_path == tech_lef
        assert 'routing_layers' in generator.layer_info
        assert 'metal1' in generator.layer_info['routing_layers']
        assert 'metal2' in generator.layer_info['routing_layers']
        
        print("✓ Initialization successful")
        print(f"  Routing layers: {generator.layer_info['routing_layers']}")
        print(f"  Default pin layer: {generator.layer_info['default_pin_layer']}")


def test_parse_def_boundary():
    """Test DEF boundary parsing"""
    print("\n" + "="*80)
    print("TEST: DEF Boundary Parsing")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test files
        tech_lef = tmpdir / "tech.lef"
        test_def = tmpdir / "partition_0.def"
        create_test_tech_lef(tech_lef)
        create_test_def(test_def)
        
        generator = MacroLEFGenerator(tech_lef)
        def_info = generator._parse_def_boundary(test_def)
        
        # Verify parsed information
        assert def_info['design_name'] == 'partition_0'
        assert def_info['dbu'] == 1000
        assert def_info['bbox'] == (0, 0, 10000, 10000)
        assert len(def_info['pins']) == 4
        
        print("✓ DEF parsing successful")
        print(f"  Design: {def_info['design_name']}")
        print(f"  DBU: {def_info['dbu']}")
        print(f"  Bbox: {def_info['bbox']}")
        print(f"  Pins: {len(def_info['pins'])}")
        
        # Verify pin information
        for pin in def_info['pins']:
            print(f"    - {pin['name']}: {pin['direction']}, layer={pin['layer']}, loc={pin['location']}")


def test_generate_macro_lef():
    """Test macro LEF generation"""
    print("\n" + "="*80)
    print("TEST: Macro LEF Generation")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test files
        tech_lef = tmpdir / "tech.lef"
        test_def = tmpdir / "partition_0.def"
        output_lef = tmpdir / "partition_0.lef"
        
        create_test_tech_lef(tech_lef)
        create_test_def(test_def)
        
        # Generate macro LEF
        generator = MacroLEFGenerator(tech_lef)
        result_path = generator.generate_macro_lef(
            partition_name="partition_0",
            def_path=test_def,
            output_path=output_lef
        )
        
        # Verify LEF file was created
        assert result_path.exists()
        assert result_path == output_lef
        
        # Verify LEF content
        with open(output_lef, 'r') as f:
            lef_content = f.read()
        
        # Check for key LEF elements
        assert 'MACRO partition_0' in lef_content
        assert 'CLASS BLOCK' in lef_content
        assert 'SIZE' in lef_content
        assert 'PIN pin_0' in lef_content
        assert 'PIN pin_1' in lef_content
        assert 'PIN pin_2' in lef_content
        assert 'PIN pin_3' in lef_content
        assert 'DIRECTION INPUT' in lef_content
        assert 'DIRECTION OUTPUT' in lef_content
        assert 'OBS' in lef_content
        assert 'END partition_0' in lef_content
        
        print("✓ Macro LEF generation successful")
        print(f"  Output: {output_lef}")
        print(f"  Size: {output_lef.stat().st_size} bytes")
        print("\n  LEF Content Preview:")
        print("  " + "-"*76)
        for i, line in enumerate(lef_content.split('\n')[:20]):
            print(f"  {line}")
        print("  " + "-"*76)


def test_batch_macro_lef_generation():
    """Test batch macro LEF generation for multiple partitions"""
    print("\n" + "="*80)
    print("TEST: Batch Macro LEF Generation")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test files
        tech_lef = tmpdir / "tech.lef"
        create_test_tech_lef(tech_lef)
        
        # Create 4 test DEF files
        partitions = {}
        for i in range(4):
            def_path = tmpdir / f"partition_{i}.def"
            create_test_def(def_path)
            partitions[i] = def_path
        
        # Generate batch macro LEFs
        output_dir = tmpdir / "lefs"
        generator = MacroLEFGenerator(tech_lef)
        lef_paths = generator.generate_batch_macro_lefs(partitions, output_dir)
        
        # Verify all LEFs were generated
        assert len(lef_paths) == 4
        for partition_id, lef_path in lef_paths.items():
            assert lef_path.exists()
            print(f"  ✓ Partition {partition_id}: {lef_path.name}")


def test_convenience_function():
    """Test the convenience function"""
    print("\n" + "="*80)
    print("TEST: Convenience Function")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test files
        tech_lef = tmpdir / "tech.lef"
        test_def = tmpdir / "partition_0.def"
        output_lef = tmpdir / "output.lef"
        
        create_test_tech_lef(tech_lef)
        create_test_def(test_def)
        
        # Use convenience function
        result_path = generate_partition_macro_lef(
            partition_name="test_partition",
            def_path=test_def,
            tech_lef_path=tech_lef,
            output_path=output_lef
        )
        
        assert result_path.exists()
        
        # Verify content has correct macro name
        with open(result_path, 'r') as f:
            content = f.read()
        
        assert 'MACRO test_partition' in content
        assert 'END test_partition' in content
        
        print("✓ Convenience function successful")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("MACRO LEF GENERATOR - UNIT TESTS")
    print("="*80)
    
    try:
        test_macro_lef_generator_init()
        test_parse_def_boundary()
        test_generate_macro_lef()
        test_batch_macro_lef_generation()
        test_convenience_function()
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED ✓")
        print("="*80)
        return True
        
    except AssertionError as e:
        print("\n" + "="*80)
        print(f"TEST FAILED ✗: {e}")
        print("="*80)
        return False
    except Exception as e:
        print("\n" + "="*80)
        print(f"ERROR: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

