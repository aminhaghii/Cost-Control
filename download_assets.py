#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download all CDN assets locally for offline operation
"""

import os
import requests
from pathlib import Path

# Base paths
STATIC_DIR = Path(__file__).parent / 'static'
CSS_DIR = STATIC_DIR / 'css'
JS_DIR = STATIC_DIR / 'js'
FONTS_DIR = STATIC_DIR / 'fonts'
WEBFONTS_DIR = STATIC_DIR / 'webfonts'

# Create directories
CSS_DIR.mkdir(parents=True, exist_ok=True)
JS_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)
WEBFONTS_DIR.mkdir(parents=True, exist_ok=True)

# Files to download
DOWNLOADS = {
    # CSS Files
    'css': [
        ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.rtl.min.css', 'bootstrap.rtl.min.css'),
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/css/all.min.css', 'font-awesome.min.css'),
        ('https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css', 'select2.min.css'),
        ('https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.rtl.min.css', 'select2-bootstrap-5-theme.rtl.min.css'),
    ],
    # JS Files
    'js': [
        ('https://code.jquery.com/jquery-3.7.1.min.js', 'jquery-3.7.1.min.js'),
        ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js', 'bootstrap.bundle.min.js'),
        ('https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js', 'select2.min.js'),
        ('https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js', 'chart.umd.min.js'),
    ],
    # Font Awesome Webfonts (using jsdelivr mirror)
    'webfonts': [
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-solid-900.woff2', 'fa-solid-900.woff2'),
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-regular-400.woff2', 'fa-regular-400.woff2'),
        ('https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/webfonts/fa-brands-400.woff2', 'fa-brands-400.woff2'),
    ],
    # Vazir Font
    'fonts': [
        ('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/webfonts/Vazirmatn-Regular.woff2', 'Vazirmatn-Regular.woff2'),
        ('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/webfonts/Vazirmatn-Bold.woff2', 'Vazirmatn-Bold.woff2'),
    ]
}

def download_file(url, filepath):
    """Download a file from URL to filepath with retry"""
    # Skip if file already exists and is not empty
    if filepath.exists() and filepath.stat().st_size > 0:
        print(f'Skipping {filepath.name} (already exists, {filepath.stat().st_size} bytes)')
        return True
    
    for attempt in range(3):
        try:
            if attempt > 0:
                print(f'  Retry {attempt}/3...', end=' ')
            else:
                print(f'Downloading {filepath.name}...', end=' ')
            
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f'✓ ({len(response.content)} bytes)')
            return True
        except Exception as e:
            if attempt == 2:
                print(f'✗ Error: {str(e)[:80]}')
                return False
            print(f'✗', end=' ')
    return False

def main():
    print('='*60)
    print('Downloading CDN Assets for Offline Operation')
    print('='*60)
    
    success_count = 0
    fail_count = 0
    
    # Download CSS files
    print('\n📄 CSS Files:')
    for url, filename in DOWNLOADS['css']:
        filepath = CSS_DIR / filename
        if download_file(url, filepath):
            success_count += 1
        else:
            fail_count += 1
    
    # Download JS files
    print('\n📜 JavaScript Files:')
    for url, filename in DOWNLOADS['js']:
        filepath = JS_DIR / filename
        if download_file(url, filepath):
            success_count += 1
        else:
            fail_count += 1
    
    # Download webfonts
    print('\n🔤 Font Awesome Webfonts:')
    for url, filename in DOWNLOADS['webfonts']:
        filepath = WEBFONTS_DIR / filename
        if download_file(url, filepath):
            success_count += 1
        else:
            fail_count += 1
    
    # Download Vazir fonts
    print('\n✨ Vazir Persian Fonts:')
    for url, filename in DOWNLOADS['fonts']:
        filepath = FONTS_DIR / filename
        if download_file(url, filepath):
            success_count += 1
        else:
            fail_count += 1
    
    print('\n' + '='*60)
    print(f'Download Complete: {success_count} succeeded, {fail_count} failed')
    print('='*60)
    
    if fail_count > 0:
        print('\n⚠️  Some files failed to download.')
        print('Please check your internet connection and try again.')
    else:
        print('\n✅ All assets downloaded successfully!')
        print('Next step: Update templates to use local files.')

if __name__ == '__main__':
    main()
