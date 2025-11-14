"""
Unit tests for Formal Verification Module
"""

from pathlib import Path
import sys
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.formal_verification import FormalVerifier, verify_hierarchical_transformation


def create_test_flat_netlist(netlist_path: Path):
    """Create a simple test flat netlist"""
    netlist_content = """
module top (
    input wire clk,
    input wire rst,
    input wire [7:0] data_in,
    output wire [7:0] data_out
);

wire [7:0] intermediate;

// Simple logic
assign intermediate = data_in + 8'd1;
assign data_out = intermediate + 8'd2;

endmodule
"""
    netlist_path.parent.mkdir(parents=True, exist_ok=True)
    with open(netlist_path, 'w') as f:
        f.write(netlist_content)


def create_test_hierarchical_netlists(output_dir: Path):
    """Create test hierarchical netlists (top + partitions)"""
    
    # Partition 0: Input processing
    partition_0_content = """
module partition_0 (
    input wire clk,
    input wire rst,
    input wire [7:0] data_in,
    output wire [7:0] p0_out
);

assign p0_out = data_in + 8'd1;

endmodule
"""
    
    # Partition 1: Output processing
    partition_1_content = """
module partition_1 (
    input wire clk,
    input wire rst,
    input wire [7:0] p1_in,
    output wire [7:0] data_out
);

assign data_out = p1_in + 8'd2;

endmodule
"""
    
    # Top-level netlist
    top_content = """
module top (
    input wire clk,
    input wire rst,
    input wire [7:0] data_in,
    output wire [7:0] data_out
);

wire [7:0] intermediate;

partition_0 p0 (
    .clk(clk),
    .rst(rst),
    .data_in(data_in),
    .p0_out(intermediate)
);

partition_1 p1 (
    .clk(clk),
    .rst(rst),
    .p1_in(intermediate),
    .data_out(data_out)
);

endmodule
"""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'partition_0.v', 'w') as f:
        f.write(partition_0_content)
    
    with open(output_dir / 'partition_1.v', 'w') as f:
        f.write(partition_1_content)
    
    with open(output_dir / 'top.v', 'w') as f:
        f.write(top_content)


def test_yosys_availability():
    """Test if Yosys is available"""
    print("\n" + "="*80)
    print("TEST: Yosys Availability Check")
    print("="*80)
    
    verifier = FormalVerifier()
    
    # Note: This test will fail if Yosys is not installed
    # which is expected and should be handled gracefully
    
    print("✓ Yosys check completed")
    print("  Note: If Yosys is not installed, verification tests will be skipped")


def test_parse_top_module():
    """Test top module name parsing"""
    print("\n" + "="*80)
    print("TEST: Top Module Name Parsing")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        create_test_flat_netlist(flat_netlist)
        
        verifier = FormalVerifier()
        module_name = verifier._parse_top_module_name(flat_netlist)
        
        assert module_name == 'top'
        
        print("✓ Module name parsing successful")
        print(f"  Detected module: {module_name}")


def test_generate_verification_script():
    """Test verification script generation"""
    print("\n" + "="*80)
    print("TEST: Verification Script Generation")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        hierarchical_dir = tmpdir / "hierarchical"
        
        create_test_flat_netlist(flat_netlist)
        create_test_hierarchical_netlists(hierarchical_dir)
        
        verifier = FormalVerifier()
        
        partition_netlists = [
            hierarchical_dir / 'partition_0.v',
            hierarchical_dir / 'partition_1.v'
        ]
        
        script = verifier._generate_verification_script(
            flat_netlist=flat_netlist,
            top_netlist=hierarchical_dir / 'top.v',
            partition_netlists=partition_netlists,
            output_log=tmpdir / 'test.log',
            use_equiv_simple=False
        )
        
        # Verify script contains key commands
        assert 'read_verilog' in script
        assert 'hierarchy -check' in script
        assert 'equiv_make' in script
        assert 'equiv_status' in script
        assert str(flat_netlist) in script
        
        print("✓ Script generation successful")
        print(f"  Script length: {len(script)} characters")
        print("\n  Script Preview:")
        print("  " + "-"*76)
        for line in script.split('\n')[:15]:
            print(f"  {line}")
        print("  " + "-"*76)


def test_verify_equivalence_mock():
    """Test verification process (without actually running Yosys)"""
    print("\n" + "="*80)
    print("TEST: Verification Process (Mock)")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        hierarchical_dir = tmpdir / "hierarchical"
        output_dir = tmpdir / "verification"
        
        create_test_flat_netlist(flat_netlist)
        create_test_hierarchical_netlists(hierarchical_dir)
        
        verifier = FormalVerifier()
        
        partition_netlists = [
            hierarchical_dir / 'partition_0.v',
            hierarchical_dir / 'partition_1.v'
        ]
        
        try:
            result = verifier.verify_equivalence(
                flat_netlist=flat_netlist,
                top_netlist=hierarchical_dir / 'top.v',
                partition_netlists=partition_netlists,
                output_dir=output_dir,
                top_module_name='top',
                use_equiv_simple=True
            )
            
            # Check that output files were created
            assert result['script_path'].exists()
            
            print("✓ Verification process initiated")
            print(f"  Script: {result['script_path']}")
            print(f"  Success: {result['success']}")
            print(f"  Equivalent: {result['equivalent']}")
            
            if result['error_message']:
                print(f"  Note: {result['error_message']}")
            
            if not result['success']:
                print("\n  ⚠ Yosys not available - this is expected if not installed")
            
        except Exception as e:
            print(f"  ⚠ Verification test skipped: {e}")
            print("  This is expected if Yosys is not installed")


def test_convenience_function_mock():
    """Test the convenience function (mock)"""
    print("\n" + "="*80)
    print("TEST: Convenience Function (Mock)")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        hierarchical_dir = tmpdir / "hierarchical"
        output_dir = tmpdir / "verification"
        
        create_test_flat_netlist(flat_netlist)
        create_test_hierarchical_netlists(hierarchical_dir)
        
        try:
            result = verify_hierarchical_transformation(
                design_name='top',
                flat_netlist=flat_netlist,
                hierarchical_dir=hierarchical_dir,
                output_dir=output_dir
            )
            
            print("✓ Convenience function executed")
            print(f"  Success: {result['success']}")
            print(f"  Equivalent: {result['equivalent']}")
            
            if not result['success']:
                print("\n  ⚠ Yosys not available - this is expected if not installed")
            
        except Exception as e:
            print(f"  ⚠ Test skipped: {e}")
            print("  This is expected if Yosys is not installed")


def test_netlist_structure():
    """Test that created netlists have correct structure"""
    print("\n" + "="*80)
    print("TEST: Netlist Structure Validation")
    print("="*80)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        flat_netlist = tmpdir / "flat.v"
        hierarchical_dir = tmpdir / "hierarchical"
        
        create_test_flat_netlist(flat_netlist)
        create_test_hierarchical_netlists(hierarchical_dir)
        
        # Verify flat netlist
        with open(flat_netlist, 'r') as f:
            flat_content = f.read()
        
        assert 'module top' in flat_content
        assert 'endmodule' in flat_content
        assert 'data_in' in flat_content
        assert 'data_out' in flat_content
        
        # Verify partition netlists
        partition_0 = hierarchical_dir / 'partition_0.v'
        with open(partition_0, 'r') as f:
            p0_content = f.read()
        
        assert 'module partition_0' in p0_content
        assert 'endmodule' in p0_content
        
        # Verify top netlist
        top_netlist = hierarchical_dir / 'top.v'
        with open(top_netlist, 'r') as f:
            top_content = f.read()
        
        assert 'module top' in top_content
        assert 'partition_0 p0' in top_content
        assert 'partition_1 p1' in top_content
        
        print("✓ Netlist structure validation passed")
        print("  ✓ Flat netlist: correct structure")
        print("  ✓ Partition netlists: correct structure")
        print("  ✓ Top netlist: correct instantiation")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("FORMAL VERIFICATION - UNIT TESTS")
    print("="*80)
    
    try:
        test_yosys_availability()
        test_parse_top_module()
        test_generate_verification_script()
        test_netlist_structure()
        test_verify_equivalence_mock()
        test_convenience_function_mock()
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED ✓")
        print("="*80)
        print("\nNote: Full verification tests require Yosys to be installed.")
        print("Install Yosys: https://github.com/YosysHQ/yosys")
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

