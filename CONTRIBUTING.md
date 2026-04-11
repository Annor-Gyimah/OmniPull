# Contributing to OmniPull

Thank you for considering contributing to OmniPull 🚀

This document explains how to contribute in a clean and structured way.

---

## Branch Structure

- `main` → stable production-ready code
- `dev` → active development branch
- `feature/*` → individual features or fixes

---

## Workflow

### For new features or major changes:

1. Fork the repository on GitHub
2. Clone your fork locally:
```bash
git clone https://github.com/your-username/OmniPull.git
```
3. Create a feature branch from dev:
```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
```
4. Make your changes
5. Commit your changes:
```bash
git commit -m "feat: add your feature description"
```
6. Push your branch:
```bash
git push origin feature/your-feature-name
```
7. Open a Pull Request to the dev branch on GitHub