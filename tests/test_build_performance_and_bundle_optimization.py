import json
import os
import re
from pathlib import Path

WEB_DIR = Path("/Users/a7890/src/my-e-car/ev-stealth-web")
ROOT_DIR = Path("/Users/a7890/src/my-e-car")

def test_package_json_dependencies_and_scripts():
    pkg_path = WEB_DIR / "package.json"
    assert pkg_path.exists(), "ev-stealth-web/package.json must exist"
    
    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)
        
    scripts = pkg.get("scripts", {})
    assert "build" in scripts, "build script must exist"
    assert "analyze" in scripts, "analyze script must exist"
    assert "lint" in scripts, "lint script must exist"
    assert "typecheck" in scripts, "typecheck script must exist"
    
    deps = pkg.get("dependencies", {})
    assert "next" in deps, "next must be in dependencies"
    assert "react" in deps, "react must be in dependencies"
    assert "react-dom" in deps, "react-dom must be in dependencies"
    
    dev_deps = pkg.get("devDependencies", {})
    assert "@next/bundle-analyzer" in dev_deps, "@next/bundle-analyzer must be in devDependencies"


def test_next_config_options_and_headers():
    config_path = WEB_DIR / "next.config.mjs"
    assert config_path.exists(), "next.config.mjs must exist"
    
    content = config_path.read_text(encoding="utf-8")
    
    # 1. Verification of NEXT_DIST_DIR support for isolated swarm/CI builds
    assert "distDir: process.env.NEXT_DIST_DIR || '.next'" in content, "distDir must support NEXT_DIST_DIR fallback"
    
    # 2. Production safety
    assert "productionBrowserSourceMaps: false" in content, "Source maps must be disabled in production"
    assert "compress: true" in content, "Gzip/brotli compression must be enabled"
    assert "ignoreBuildErrors: false" in content, "Typecheck errors must never be ignored during build"
    assert "ignoreDuringBuilds: false" in content, "ESLint errors must never be ignored during build"
    
    # 3. Image optimization & caching
    assert "minimumCacheTTL: 86400" in content, "minimumCacheTTL must be at least 86400s (24h)"
    assert "'image/avif'" in content and "'image/webp'" in content, "AVIF and WebP must be configured formats"
    
    # 4. Security & Caching Headers
    assert "X-Content-Type-Options" in content, "nosniff header must be present"
    assert "X-Frame-Options" in content, "DENY header must be present"
    assert "Strict-Transport-Security" in content, "HSTS must be present"
    assert "secret-admin-reports" in content, "Secret admin reports must have noindex header"
    assert "noindex, nofollow" in content, "Robots tag must block indexing of secret admin reports"
    assert "_next/static/:path*" in content, "Static chunks must have 1-year immutable cache"
    assert "max-age=31536000, immutable" in content, "Immutable caching must be enforced"


def test_client_components_zero_heavy_static_json_bundling():
    """Verify that client components do NOT import heavy static JSON files directly or via server loaders."""
    client_files = [
        WEB_DIR / "src/app/subsidy-tracker/SubsidyTrackerClient.tsx",
        WEB_DIR / "src/app/secret-admin-reports/AdminDashboardClient.tsx",
        WEB_DIR / "src/app/recall-portal/RecallPortalClient.tsx",
        WEB_DIR / "src/app/reliability-analytics/ReliabilityDashboardClient.tsx",
        WEB_DIR / "src/app/depreciation-calculator/DepreciationCalculatorClient.tsx",
    ]
    
    for client_path in client_files:
        assert client_path.exists(), f"{client_path} must exist"
        code = client_path.read_text(encoding="utf-8")
        # Ensure no client component imports raw data JSON files
        assert "from '../data/" not in code, f"{client_path} must not import ../data/*.json"
        assert "from '@/data/" not in code, f"{client_path} must not import @/data/*.json"
        
    # Specifically verify SubsidyTrackerClient does not import server-side getSubsidyData.ts
    subsidy_client_code = (WEB_DIR / "src/app/subsidy-tracker/SubsidyTrackerClient.tsx").read_text(encoding="utf-8")
    assert "from '@/lib/getSubsidyData'" not in subsidy_client_code, "SubsidyTrackerClient must not import getSubsidyData"
    
    # Specifically verify AdminDashboardClient does not import server-side getDailyReports.ts
    admin_client_code = (WEB_DIR / "src/app/secret-admin-reports/AdminDashboardClient.tsx").read_text(encoding="utf-8")
    assert "from '@/lib/getDailyReports'" not in admin_client_code, "AdminDashboardClient must not import getDailyReports"


def test_modular_calculation_engines_parity():
    """Verify clean separation between calculation engines and server data loaders."""
    modules = [
        ("subsidyCalculations.ts", "getSubsidyData.ts"),
        ("recallCalculations.ts", "getRecallData.ts"),
        ("reliabilityCalculations.ts", "getReliabilityData.ts"),
        ("depreciationCalculations.ts", "getDepreciationData.ts"),
        ("reportCalculations.ts", "getDailyReports.ts"),
    ]
    
    for calc_name, loader_name in modules:
        calc_path = WEB_DIR / "src/lib" / calc_name
        loader_path = WEB_DIR / "src/lib" / loader_name
        
        assert calc_path.exists(), f"{calc_name} must exist"
        assert loader_path.exists(), f"{loader_name} must exist"
        
        # Calculation files must be pure and never import JSON files directly
        calc_code = calc_path.read_text(encoding="utf-8")
        assert ".json" not in calc_code, f"{calc_name} must be a pure engine without JSON imports"
