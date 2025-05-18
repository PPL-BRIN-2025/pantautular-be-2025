# Contributing to Pantau Tular Backend

Thank you for your interest in contributing to Pantau Tular Backend! This document provides guidelines for contributing to the project.

## Conventional Commits

We use [Conventional Commits](https://www.conventionalcommits.org/) to automate versioning and changelog generation. Please format your commit messages according to this specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: A new feature (minor version bump)
- `fix`: A bug fix (patch version bump)
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes that affect the build system or external dependencies
- `ci`: Changes to our CI configuration files and scripts
- `chore`: Other changes that don't modify src or test files

### TDD-Style Commits

We also support Test-Driven Development style commits:

- `red:` Writing a failing test (no version bump)
- `green:` Making the test pass with new functionality (minor version bump)
- `refactor:` Improving the code without changing functionality (patch version bump)

### Breaking Changes

For breaking changes, add an exclamation mark after the type/scope or add "BREAKING CHANGE:" in the footer:

```
feat!: add new required parameter to authentication

BREAKING CHANGE: The authentication now requires an API key
```

This will trigger a major version bump.

### Examples

```
feat: add health check endpoint
fix: resolve database connection issue
docs: update README with Docker instructions
refactor: optimize database queries
feat(auth): implement JWT authentication

# TDD-style examples
red: add test for user profile API
green: implement user profile API
refactor: optimize database queries in user profile API
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes using conventional commits
4. Push to your branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Automated Versioning

Our CI system automatically:
1. Analyzes commit messages since the last release
2. Determines the appropriate version bump (major, minor, patch)
3. Updates the VERSION file and CHANGELOG.md
4. Creates a new release

No manual version updates are needed when using conventional commits.

### Version Bump Rules

- Major version (1.0.0 → 2.0.0): Breaking changes (`feat!:`, `fix!:`, or footer with `BREAKING CHANGE:`)
- Minor version (1.0.0 → 1.1.0): New features (`feat:` or `green:`)
- Patch version (1.0.0 → 1.0.1): Bug fixes or refactoring (`fix:` or `refactor:`)
- No version bump: Documentation, tests, chores, or red commits (`docs:`, `test:`, `chore:`, `red:`, etc.) 