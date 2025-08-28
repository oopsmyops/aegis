# AEGIS Release Checklist

This document outlines the complete process for creating a new AEGIS CLI release with multi-architecture binaries.

## Pre-Release Checklist

### 🧪 Testing & Quality Assurance
- [ ] All CI tests pass on main branch
- [ ] Integration tests pass with real AWS Bedrock
- [ ] Manual testing completed on all target platforms
- [ ] Performance benchmarks within acceptable limits
- [ ] Security scans pass (no critical vulnerabilities)
- [ ] Documentation is up to date

### 📝 Documentation Updates
- [ ] README.md updated with new features
- [ ] CHANGELOG.md updated with release notes
- [ ] API documentation updated (if applicable)
- [ ] Configuration examples updated
- [ ] Installation instructions verified

### 🔧 Code Preparation
- [ ] Version number updated in `setup.py`
- [ ] All dependencies are up to date and compatible
- [ ] No debug code or temporary changes in main branch
- [ ] Code formatting and linting checks pass

## Release Process

### 1. Version Tagging

Choose the appropriate version number following [Semantic Versioning](https://semver.org/):
- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

```bash
# Create and push version tag
git tag -a v1.2.3 -m "Release version 1.2.3"
git push origin v1.2.3
```

### 2. Automated Release (Recommended)

The GitHub Actions workflow will automatically:
1. Run comprehensive tests
2. Build binaries for all supported platforms
3. Generate checksums and metadata
4. Create GitHub release with assets
5. Upload all binaries and documentation

**Supported Platforms:**
- Linux x64 (`aegis-linux-x64`)
- Linux ARM64 (`aegis-linux-arm64`)
- macOS x64 (`aegis-macos-x64`) - Intel Macs
- macOS ARM64 (`aegis-macos-arm64`) - Apple Silicon
- Windows x64 (`aegis-windows-x64.exe`)

### 3. Manual Release (Alternative)

If needed, you can trigger a manual release:

```bash
# Go to GitHub Actions
# Select "Build and Release Multi-Arch Binaries" workflow
# Click "Run workflow"
# Enter version (e.g., v1.2.3)
# Select if it's a pre-release
# Click "Run workflow"
```

## Post-Release Checklist

### 📦 Release Verification
- [ ] All binary downloads work correctly
- [ ] Checksums match generated files
- [ ] Binaries execute on target platforms
- [ ] Help and version commands work
- [ ] Release notes are accurate and complete

### 📢 Communication
- [ ] Release announcement prepared
- [ ] Documentation sites updated
- [ ] Community notifications sent (if applicable)
- [ ] Social media updates (if applicable)

### 🔄 Follow-up Tasks
- [ ] Monitor for bug reports
- [ ] Update package managers (if applicable)
- [ ] Plan next release cycle
- [ ] Update project roadmap

## Release Types

### 🚀 Stable Release
- Thoroughly tested
- All features complete
- Documentation complete
- Suitable for production use

### 🧪 Pre-Release (Alpha/Beta/RC)
- New features under testing
- May contain bugs
- Documentation may be incomplete
- For testing and feedback only

### 🔧 Hotfix Release
- Critical bug fixes only
- Minimal changes from previous stable
- Fast-track testing process
- Immediate deployment recommended

## Binary Verification

Users can verify downloaded binaries using provided checksums:

```bash
# Verify SHA256 checksum
sha256sum -c aegis-linux-x64.sha256

# Verify MD5 checksum
md5sum -c aegis-linux-x64.md5
```

## Rollback Procedure

If a release has critical issues:

1. **Immediate Actions:**
   - Mark release as pre-release in GitHub
   - Add warning to release notes
   - Communicate issue to users

2. **Create Hotfix:**
   - Create hotfix branch from previous stable tag
   - Apply minimal fix
   - Follow expedited release process

3. **Full Rollback:**
   - Delete problematic release
   - Restore previous version as latest
   - Communicate rollback to users

## Troubleshooting

### Build Failures
- Check CI logs for specific errors
- Verify all dependencies are available
- Ensure PyInstaller compatibility
- Test locally on target platform

### Binary Issues
- Verify all hidden imports are included
- Check for missing data files
- Test on clean system without development dependencies
- Validate binary permissions and execution

### Release Upload Failures
- Check GitHub token permissions
- Verify artifact sizes (GitHub has limits)
- Ensure network connectivity
- Retry with manual upload if needed

## Automation Details

### GitHub Actions Workflows

1. **CI Workflow** (`ci.yml`)
   - Runs on every push/PR
   - Tests multiple Python versions
   - Performs security scans
   - Validates code quality

2. **Release Workflow** (`release.yml`)
   - Triggered by version tags
   - Builds multi-arch binaries
   - Creates GitHub releases
   - Uploads all assets

3. **Benchmark Workflow** (`benchmark.yml`)
   - Performance monitoring
   - Binary size tracking
   - Memory usage analysis

### Build Matrix

The release workflow builds binaries for:
- **Operating Systems**: Linux, macOS, Windows
- **Architectures**: x64, ARM64 (where supported)
- **Python Version**: 3.11 (embedded in binary)

### Security Features

- All binaries include SHA256 and MD5 checksums
- Security scans run on every build
- Dependency vulnerability checks
- Code quality analysis

## Support

For release-related issues:
1. Check existing GitHub Issues
2. Review workflow logs
3. Contact maintainers
4. Create detailed bug report

---

**Remember**: Always test releases thoroughly before marking them as stable!