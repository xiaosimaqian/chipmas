"""
Formal Verification Module

This module provides formal equivalence checking between flat and hierarchical netlists
using Yosys (open-source synthesis tool with formal verification capabilities).

Key Features:
- Verifies functional equivalence of flat vs. hierarchical netlists
- Uses Yosys formal verification flow
- Generates detailed verification reports
- Supports incremental verification for large designs
"""

from typing import Dict, List, Tuple, Optional
from pathlib import Path
import subprocess
import re
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FormalVerifier:
    """
    Formal equivalence checker using Yosys
    
    Workflow:
    1. Read flat netlist (original design)
    2. Read hierarchical netlist (top + partitions)
    3. Run equivalence check
    4. Report results
    """
    
    def __init__(self, yosys_path: str = 'yosys'):
        """
        Initialize the formal verifier
        
        Args:
            yosys_path: Path to Yosys executable (default: 'yosys' in PATH)
        """
        self.yosys_path = yosys_path
        self._check_yosys_available()
    
    def _check_yosys_available(self) -> bool:
        """
        Check if Yosys is installed and available
        
        Returns:
            True if Yosys is available, False otherwise
        """
        try:
            result = subprocess.run(
                [self.yosys_path, '-V'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version_match = re.search(r'Yosys\s+([\d.]+)', result.stdout)
                if version_match:
                    logger.info(f"Yosys version {version_match.group(1)} found")
                    return True
            
            logger.error("Yosys not found or not working properly")
            return False
            
        except FileNotFoundError:
            logger.error(f"Yosys executable not found: {self.yosys_path}")
            logger.error("Please install Yosys: https://github.com/YosysHQ/yosys")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Yosys command timed out")
            return False
    
    def _generate_verification_script(
        self,
        flat_netlist: Path,
        top_netlist: Path,
        partition_netlists: List[Path],
        output_log: Path,
        use_equiv_simple: bool = False
    ) -> str:
        """
        Generate Yosys script for equivalence checking
        
        Args:
            flat_netlist: Path to original flat netlist
            top_netlist: Path to hierarchical top netlist
            partition_netlists: List of partition netlist paths
            output_log: Path to save verification log
            use_equiv_simple: Use simple equivalence check (faster, less rigorous)
            
        Returns:
            Yosys script as string
        """
        script_lines = [
            "# Formal Verification Script",
            f"# Generated: {datetime.now().isoformat()}",
            "#",
            f"# Flat netlist: {flat_netlist}",
            f"# Top netlist: {top_netlist}",
            f"# Partitions: {len(partition_netlists)}",
            "",
            "# Read flat design (gold)",
            f"read_verilog {flat_netlist}",
            "hierarchy -top {top_module}",  # 去掉-check，允许标准单元作为黑盒
            "proc; opt_clean",
            "flatten",
            "rename -top gold",
            "",
            "# Read hierarchical design (gate)",
            "design -stash gold_design",
            "design -push"
        ]
        
        # Read all partition netlists first
        for partition_netlist in partition_netlists:
            script_lines.append(f"read_verilog {partition_netlist}")
        
        # Then read top netlist
        script_lines.append(f"read_verilog {top_netlist}")
        
        script_lines.extend([
            "hierarchy -top {top_module}",  # 去掉-check，允许标准单元作为黑盒
            "proc; opt_clean",
            "flatten",
            "rename -top gate",
            "",
            "# Load gold design",
            "design -copy-from gold_design gold",
            "",
            "# Prepare for equivalence check",
            "design -save gate_design",
            ""
        ])
        
        if use_equiv_simple:
            # Simple equivalence check (faster)
            script_lines.extend([
                "# Simple equivalence check",
                "equiv_make gold gate equiv",
                "equiv_simple",
                "equiv_status -assert"
            ])
        else:
            # Full equivalence check (more rigorous)  
            script_lines.extend([
                "# Full equivalence check",
                "equiv_make gold gate equiv",
                "equiv_simple",
                "equiv_induct",
                "equiv_status -assert"
            ])
        
        script_lines.extend([
            "",
            "# Print final status",
            "equiv_status",
            ""
        ])
        
        return '\n'.join(script_lines)
    
    def _parse_top_module_name(self, netlist_path: Path) -> Optional[str]:
        """
        Parse the top module name from a Verilog file
        
        Args:
            netlist_path: Path to Verilog netlist
            
        Returns:
            Top module name, or None if not found
        """
        try:
            with open(netlist_path, 'r') as f:
                content = f.read()
            
            # Find module declarations
            module_pattern = r'module\s+(\w+)\s*(?:\(|;)'
            matches = re.findall(module_pattern, content)
            
            if matches:
                # Return the first module (typically the top)
                return matches[0]
            
        except Exception as e:
            logger.error(f"Error parsing module name from {netlist_path}: {e}")
        
        return None
    
    def verify_equivalence(
        self,
        flat_netlist: Path,
        top_netlist: Path,
        partition_netlists: List[Path],
        output_dir: Path,
        top_module_name: Optional[str] = None,
        use_equiv_simple: bool = False
    ) -> Dict:
        """
        Run formal equivalence check
        
        Args:
            flat_netlist: Path to original flat netlist
            top_netlist: Path to hierarchical top netlist
            partition_netlists: List of partition netlist paths
            output_dir: Directory for output files
            top_module_name: Top module name (auto-detect if None)
            use_equiv_simple: Use simple equivalence check
            
        Returns:
            Verification result dictionary:
            {
                'success': bool,
                'equivalent': bool,
                'error_message': str,
                'log_path': Path,
                'script_path': Path,
                'runtime': float
            }
        """
        logger.info("Starting formal equivalence verification...")
        logger.info(f"  Flat netlist: {flat_netlist}")
        logger.info(f"  Top netlist: {top_netlist}")
        logger.info(f"  Partitions: {len(partition_netlists)}")
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Auto-detect top module name if not provided
        if top_module_name is None:
            top_module_name = self._parse_top_module_name(flat_netlist)
            if top_module_name is None:
                return {
                    'success': False,
                    'equivalent': False,
                    'error_message': 'Could not detect top module name',
                    'log_path': None,
                    'script_path': None,
                    'runtime': 0.0
                }
            logger.info(f"  Auto-detected top module: {top_module_name}")
        
        # Prepare paths
        script_path = output_dir / 'verification.ys'
        log_path = output_dir / 'verification.log'
        report_path = output_dir / 'verification_report.json'
        
        # Generate Yosys script
        script_content = self._generate_verification_script(
            flat_netlist=flat_netlist,
            top_netlist=top_netlist,
            partition_netlists=partition_netlists,
            output_log=log_path,
            use_equiv_simple=use_equiv_simple
        )
        
        # Replace {top_module} placeholder
        script_content = script_content.replace('{top_module}', top_module_name)
        
        # Write script to file
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        logger.info(f"Verification script saved: {script_path}")
        
        # Run Yosys
        start_time = datetime.now()
        
        try:
            result = subprocess.run(
                [self.yosys_path, '-s', str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            runtime = (datetime.now() - start_time).total_seconds()
            
            # Write full log
            with open(log_path, 'w') as f:
                f.write(result.stdout)
            
            # Parse results
            # Note: Yosys returns non-zero when equiv_status -assert fails (designs are not equivalent)
            # This is expected behavior, not an error
            success = True  # We consider it successful if Yosys ran
            equivalent = False
            error_message = None
            
            # Check for equivalence in output
            if result.returncode == 0:
                # Return code 0 means assertion passed (designs are equivalent)
                equivalent = True
                logger.info("✓ Equivalence verified successfully!")
            elif 'Assertion failed' in result.stdout or 'ERROR' in result.stdout:
                # Yosys detected non-equivalence
                equivalent = False
                error_message = "Designs are NOT equivalent (as detected by Yosys)"
                logger.info("✓ Yosys correctly detected non-equivalence")
            else:
                # Some other error
                success = False
                error_message = f"Yosys execution failed with code {result.returncode}"
                logger.error(error_message)
            
            # Generate report
            report = {
                'timestamp': datetime.now().isoformat(),
                'success': success,
                'equivalent': equivalent,
                'error_message': error_message,
                'flat_netlist': str(flat_netlist),
                'top_netlist': str(top_netlist),
                'partition_netlists': [str(p) for p in partition_netlists],
                'top_module': top_module_name,
                'runtime_seconds': runtime,
                'log_path': str(log_path),
                'script_path': str(script_path)
            }
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Verification completed in {runtime:.2f}s")
            logger.info(f"Report saved: {report_path}")
            
            return {
                'success': success,
                'equivalent': equivalent,
                'error_message': error_message,
                'log_path': log_path,
                'script_path': script_path,
                'report_path': report_path,
                'runtime': runtime
            }
            
        except subprocess.TimeoutExpired:
            runtime = (datetime.now() - start_time).total_seconds()
            error_message = f"Verification timed out after {runtime:.2f}s"
            logger.error(error_message)
            
            return {
                'success': False,
                'equivalent': False,
                'error_message': error_message,
                'log_path': log_path,
                'script_path': script_path,
                'runtime': runtime
            }
        
        except Exception as e:
            runtime = (datetime.now() - start_time).total_seconds()
            error_message = f"Verification error: {str(e)}"
            logger.error(error_message)
            
            return {
                'success': False,
                'equivalent': False,
                'error_message': error_message,
                'log_path': log_path,
                'script_path': script_path,
                'runtime': runtime
            }


def verify_hierarchical_transformation(
    design_name: str,
    flat_netlist: Path,
    hierarchical_dir: Path,
    output_dir: Path
) -> Dict:
    """
    Convenience function to verify a hierarchical transformation
    
    Args:
        design_name: Name of the design
        flat_netlist: Path to original flat netlist
        hierarchical_dir: Directory containing top netlist and partition netlists
        output_dir: Directory for verification outputs
        
    Returns:
        Verification result dictionary
    """
    # Find top netlist and partition netlists
    top_netlist = hierarchical_dir / f"{design_name}_top.v"
    
    if not top_netlist.exists():
        # Try alternative naming
        top_netlist = hierarchical_dir / "top.v"
        if not top_netlist.exists():
            raise FileNotFoundError(f"Top netlist not found in {hierarchical_dir}")
    
    # Find all partition netlists
    partition_netlists = list(hierarchical_dir.glob("partition_*.v"))
    
    if not partition_netlists:
        raise FileNotFoundError(f"No partition netlists found in {hierarchical_dir}")
    
    logger.info(f"Found {len(partition_netlists)} partition netlists")
    
    # Run verification
    verifier = FormalVerifier()
    return verifier.verify_equivalence(
        flat_netlist=flat_netlist,
        top_netlist=top_netlist,
        partition_netlists=partition_netlists,
        output_dir=output_dir
    )


if __name__ == '__main__':
    # Test example
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 4:
        print("Usage: python formal_verification.py <flat_netlist> <hierarchical_dir> <output_dir>")
        print("")
        print("Example:")
        print("  python formal_verification.py \\")
        print("    data/ispd2015/mgc_fft_1/design.v \\")
        print("    results/hierarchical/mgc_fft_1 \\")
        print("    results/verification/mgc_fft_1")
        sys.exit(1)
    
    flat_netlist = Path(sys.argv[1])
    hierarchical_dir = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])
    
    # Extract design name from flat netlist
    design_name = flat_netlist.stem
    
    result = verify_hierarchical_transformation(
        design_name=design_name,
        flat_netlist=flat_netlist,
        hierarchical_dir=hierarchical_dir,
        output_dir=output_dir
    )
    
    print("\n" + "="*80)
    print("VERIFICATION RESULTS")
    print("="*80)
    print(f"Success: {result['success']}")
    print(f"Equivalent: {result['equivalent']}")
    if result['error_message']:
        print(f"Error: {result['error_message']}")
    print(f"Runtime: {result['runtime']:.2f}s")
    print(f"Log: {result['log_path']}")
    print("="*80)
    
    sys.exit(0 if result['equivalent'] else 1)

