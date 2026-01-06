#!/usr/bin/env python3
"""
Excel Template Copier for PR Analysis

This script copies an existing Excel template file and updates the Power Query
data connections to point to a different repository's CSV files.

Usage:
    python copy_excel_template.py <template_file> <new_repo_name> [--output <dir>]
    
Examples:
    python copy_excel_template.py CycleTimeAnalysis.xlsx cnn-android-7
    python copy_excel_template.py /path/to/template.xlsx cnn-ios-7 --output /path/to/output/
"""

import argparse
import base64
import io
import logging
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path
from typing import Optional


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def extract_datamashup(xlsx_path: Path) -> tuple:
    """
    Extract the DataMashup content from an Excel file.
    
    Returns:
        Tuple of (datamashup_base64, original_repo_name)
    """
    logger = logging.getLogger(__name__)
    
    with zipfile.ZipFile(xlsx_path, 'r') as zf:
        # Read customXml/item1.xml which contains the DataMashup
        try:
            item1_content = zf.read('customXml/item1.xml')
        except KeyError:
            raise ValueError("No customXml/item1.xml found - this Excel file may not have Power Query connections")
        
        # Decode UTF-16
        xml_content = item1_content.decode('utf-16-le')
        
        # Extract the base64 DataMashup content
        match = re.search(r'<DataMashup[^>]*>([^<]+)</DataMashup>', xml_content)
        if not match:
            raise ValueError("No DataMashup found in customXml/item1.xml")
        
        b64_content = match.group(1)
        
        # Decode and extract the M code to find the original repo name
        decoded = base64.b64decode(b64_content)
        pkg_parts_len = struct.unpack('<I', decoded[4:8])[0]
        zip_data = decoded[8:8 + pkg_parts_len]
        
        inner_zf = zipfile.ZipFile(io.BytesIO(zip_data))
        m_content = inner_zf.read('Formulas/Section1.m').decode('utf-8')
        
        # Find the repo name from file paths like pr_tracking_<repo>.csv
        repo_match = re.search(r'pr_tracking_([^.]+)\.csv', m_content)
        if repo_match:
            original_repo = repo_match.group(1)
            logger.info(f"Found original repo: {original_repo}")
        else:
            raise ValueError("Could not find original repo name in Power Query M code")
        
        return b64_content, original_repo, xml_content


def update_datamashup(b64_content: str, old_repo: str, new_repo: str) -> str:
    """
    Update the DataMashup content to use a new repository name.
    
    Returns:
        New base64-encoded DataMashup content
    """
    logger = logging.getLogger(__name__)
    
    # Decode the base64 content
    decoded = base64.b64decode(b64_content)
    
    # Parse the header
    version = struct.unpack('<I', decoded[0:4])[0]
    pkg_parts_len = struct.unpack('<I', decoded[4:8])[0]
    
    # Extract the zip data
    zip_data = decoded[8:8 + pkg_parts_len]
    remaining_data = decoded[8 + pkg_parts_len:]
    
    # Open the inner zip
    inner_zf = zipfile.ZipFile(io.BytesIO(zip_data))
    
    # Create a new zip in memory
    new_zip_buffer = io.BytesIO()
    new_zf = zipfile.ZipFile(new_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
    
    for name in inner_zf.namelist():
        content = inner_zf.read(name)
        
        if name == 'Formulas/Section1.m':
            # Update the M code with new repo name
            m_content = content.decode('utf-8')
            
            # Replace repo name in file paths
            m_content = m_content.replace(f'pr_tracking_{old_repo}.csv', f'pr_tracking_{new_repo}.csv')
            m_content = m_content.replace(f'pr_tracking_reviewers_{old_repo}.csv', f'pr_tracking_reviewers_{new_repo}.csv')
            
            # Replace query names
            m_content = m_content.replace(f'pr_tracking_{old_repo}', f'pr_tracking_{new_repo}')
            m_content = m_content.replace(f'pr_tracking_reviewers_{old_repo}', f'pr_tracking_reviewers_{new_repo}')
            
            logger.debug(f"Updated M code:\n{m_content}")
            content = m_content.encode('utf-8')
        
        new_zf.writestr(name, content)
    
    new_zf.close()
    new_zip_data = new_zip_buffer.getvalue()
    
    # Rebuild the DataMashup binary
    new_decoded = struct.pack('<I', version)
    new_decoded += struct.pack('<I', len(new_zip_data))
    new_decoded += new_zip_data
    new_decoded += remaining_data
    
    # Re-encode to base64
    return base64.b64encode(new_decoded).decode('ascii')


def update_excel_file(xlsx_path: Path, output_path: Path, old_repo: str, new_repo: str) -> None:
    """
    Create a copy of the Excel file with updated Power Query connections.
    """
    logger = logging.getLogger(__name__)
    
    # Copy the file first
    shutil.copy2(xlsx_path, output_path)
    logger.info(f"Copied template to {output_path}")
    
    # Read and update the file
    with zipfile.ZipFile(xlsx_path, 'r') as src_zf:
        # Get list of all files
        file_list = src_zf.namelist()
        
        # Read all files into memory
        files_content = {}
        for name in file_list:
            files_content[name] = src_zf.read(name)
    
    # Update specific files
    for name in files_content:
        content = files_content[name]
        
        if name == 'customXml/item1.xml':
            # Update the DataMashup
            xml_content = content.decode('utf-16-le')
            
            # Extract and update the DataMashup
            match = re.search(r'(<DataMashup[^>]*>)([^<]+)(</DataMashup>)', xml_content)
            if match:
                prefix, b64_content, suffix = match.groups()
                new_b64 = update_datamashup(b64_content, old_repo, new_repo)
                xml_content = xml_content[:match.start()] + prefix + new_b64 + suffix + xml_content[match.end():]
            
            content = xml_content.encode('utf-16-le')
            files_content[name] = content
            logger.info("Updated customXml/item1.xml with new DataMashup")
        
        elif name == 'xl/connections.xml':
            # Update connection names
            xml_str = content.decode('utf-8')
            xml_str = xml_str.replace(old_repo, new_repo)
            # Also handle underscore version used in table names
            old_underscore = old_repo.replace('-', '_')
            new_underscore = new_repo.replace('-', '_')
            xml_str = xml_str.replace(old_underscore, new_underscore)
            files_content[name] = xml_str.encode('utf-8')
            logger.info("Updated xl/connections.xml")
        
        elif name == 'xl/workbook.xml':
            # Update any references in workbook
            xml_str = content.decode('utf-8')
            xml_str = xml_str.replace(old_repo, new_repo)
            old_underscore = old_repo.replace('-', '_')
            new_underscore = new_repo.replace('-', '_')
            xml_str = xml_str.replace(old_underscore, new_underscore)
            files_content[name] = xml_str.encode('utf-8')
            logger.info("Updated xl/workbook.xml")
        
        elif name.startswith('xl/tables/'):
            # Update table definitions
            xml_str = content.decode('utf-8')
            xml_str = xml_str.replace(old_repo, new_repo)
            old_underscore = old_repo.replace('-', '_')
            new_underscore = new_repo.replace('-', '_')
            xml_str = xml_str.replace(old_underscore, new_underscore)
            files_content[name] = xml_str.encode('utf-8')
            logger.debug(f"Updated {name}")
        
        elif name.startswith('xl/queryTables/') or name.startswith('xl/pivotCache/'):
            # Update query tables and pivot cache
            try:
                xml_str = content.decode('utf-8')
                xml_str = xml_str.replace(old_repo, new_repo)
                old_underscore = old_repo.replace('-', '_')
                new_underscore = new_repo.replace('-', '_')
                xml_str = xml_str.replace(old_underscore, new_underscore)
                files_content[name] = xml_str.encode('utf-8')
                logger.debug(f"Updated {name}")
            except:
                pass  # Skip binary files
        
        elif name == 'xl/sharedStrings.xml':
            # Update shared strings (text content)
            try:
                xml_str = content.decode('utf-8')
                xml_str = xml_str.replace(old_repo, new_repo)
                old_underscore = old_repo.replace('-', '_')
                new_underscore = new_repo.replace('-', '_')
                xml_str = xml_str.replace(old_underscore, new_underscore)
                files_content[name] = xml_str.encode('utf-8')
                logger.info("Updated xl/sharedStrings.xml")
            except:
                pass
        
        elif name.startswith('xl/charts/'):
            # Update chart definitions
            try:
                xml_str = content.decode('utf-8')
                xml_str = xml_str.replace(old_repo, new_repo)
                old_underscore = old_repo.replace('-', '_')
                new_underscore = new_repo.replace('-', '_')
                xml_str = xml_str.replace(old_underscore, new_underscore)
                files_content[name] = xml_str.encode('utf-8')
                logger.debug(f"Updated {name}")
            except:
                pass
        
        elif name.startswith('xl/tables/'):
            # Update table definitions
            try:
                xml_str = content.decode('utf-8')
                xml_str = xml_str.replace(old_repo, new_repo)
                old_underscore = old_repo.replace('-', '_')
                new_underscore = new_repo.replace('-', '_')
                xml_str = xml_str.replace(old_underscore, new_underscore)
                files_content[name] = xml_str.encode('utf-8')
                logger.debug(f"Updated {name}")
            except:
                pass
        
        elif name.startswith('xl/pivotTables/'):
            # Update pivot table definitions
            try:
                xml_str = content.decode('utf-8')
                xml_str = xml_str.replace(old_repo, new_repo)
                old_underscore = old_repo.replace('-', '_')
                new_underscore = new_repo.replace('-', '_')
                xml_str = xml_str.replace(old_underscore, new_underscore)
                files_content[name] = xml_str.encode('utf-8')
                logger.debug(f"Updated {name}")
            except:
                pass
        
        elif name == 'docProps/app.xml':
            # Update app properties (contains sheet names list)
            try:
                xml_str = content.decode('utf-8')
                xml_str = xml_str.replace(old_repo, new_repo)
                old_underscore = old_repo.replace('-', '_')
                new_underscore = new_repo.replace('-', '_')
                xml_str = xml_str.replace(old_underscore, new_underscore)
                files_content[name] = xml_str.encode('utf-8')
                logger.info("Updated docProps/app.xml")
            except:
                pass
        
        elif name.startswith('xl/worksheets/'):
            # Update worksheet definitions (may contain references)
            try:
                xml_str = content.decode('utf-8')
                if old_repo in xml_str or old_repo.replace('-', '_') in xml_str:
                    xml_str = xml_str.replace(old_repo, new_repo)
                    old_underscore = old_repo.replace('-', '_')
                    new_underscore = new_repo.replace('-', '_')
                    xml_str = xml_str.replace(old_underscore, new_underscore)
                    files_content[name] = xml_str.encode('utf-8')
                    logger.debug(f"Updated {name}")
            except:
                pass
    
    # Write the updated file
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as dst_zf:
        for name, content in files_content.items():
            dst_zf.writestr(name, content)
    
    logger.info(f"Successfully created {output_path}")


def copy_template(template_path: Path, new_repo: str, output_dir: Path) -> Optional[Path]:
    """
    Copy an Excel template and update it for a new repository.
    
    Args:
        template_path: Path to the template Excel file
        new_repo: New repository name (e.g., 'cnn-android-7')
        output_dir: Directory for the output file
        
    Returns:
        Path to the new Excel file, or None if failed
    """
    logger = logging.getLogger(__name__)
    
    if not template_path.exists():
        logger.error(f"Template file not found: {template_path}")
        return None
    
    # Extract the original repo name
    try:
        b64_content, old_repo, xml_content = extract_datamashup(template_path)
        logger.info(f"Template uses repo: {old_repo}")
    except Exception as e:
        logger.error(f"Failed to extract DataMashup: {e}")
        return None
    
    # Generate output filename
    output_path = output_dir / f"CycleTimeAnalysis_{new_repo}.xlsx"
    
    # Update and save
    try:
        update_excel_file(template_path, output_path, old_repo, new_repo)
        return output_path
    except Exception as e:
        logger.error(f"Failed to update Excel file: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Copy Excel template and update Power Query connections for a new repository',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s CycleTimeAnalysis.xlsx cnn-android-7
    %(prog)s /path/to/template.xlsx cnn-ios-7 --output /path/to/output/
    %(prog)s template.xlsx cnn-android-7 cnn-ios-7 cnn-set-top-lightning
        """
    )
    
    parser.add_argument(
        'template',
        type=str,
        help='Path to the template Excel file'
    )
    
    parser.add_argument(
        'repos',
        nargs='+',
        help='Repository name(s) to create Excel files for'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='.',
        help='Output directory for Excel files (default: current directory)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    template_path = Path(args.template).resolve()
    output_dir = Path(args.output).resolve()
    
    if not template_path.exists():
        logger.error(f"Template file not found: {template_path}")
        return 1
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Template: {template_path}")
    logger.info(f"Output directory: {output_dir}")
    
    success_count = 0
    failed_repos = []
    
    for repo_name in args.repos:
        try:
            result = copy_template(template_path, repo_name, output_dir)
            if result:
                success_count += 1
                print(f"✅ Created: {result}")
            else:
                failed_repos.append(repo_name)
                print(f"❌ Failed: {repo_name}")
        except Exception as e:
            logger.error(f"Error creating file for {repo_name}: {e}")
            failed_repos.append(repo_name)
            print(f"❌ Failed: {repo_name} ({e})")
    
    print(f"\n📊 Summary: {success_count}/{len(args.repos)} files created")
    
    if failed_repos:
        print(f"Failed repos: {', '.join(failed_repos)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

