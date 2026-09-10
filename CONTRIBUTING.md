# Contributing to Allomorph

Thank you for your interest in contributing to **Allomorph**! We welcome contributions ranging from new SPICE netlists and pickup profiles to performance optimizations in the native simulation engine, physical acoustics math, and documentation.

---

## 1. Contributor License Agreement (CLA)

Allomorph is distributed under the [PolyForm Noncommercial License 1.0.0](LICENSE) for the community and is dual-licensed for commercial deployments.

To ensure that contributions can be safely integrated, distributed, and maintained under both open and commercial terms, **all contributors must agree to the [Allomorph Contributor License Agreement (CLA)](CLA.md)**.

### How to Sign the CLA
You do not need to sign a separate paper form. Simply include a standard Git Developer Certificate of Origin / CLA sign-off line in your commit message:

```bash
git commit -s -m "feat(circuits): add vintage Thunderbird humbucker netlist"
```
Or include the line in your commit message / pull request description:
```
Signed-off-by: Your Legal Name <your.email@example.com>
```

By including this line, you certify that your contribution complies with the terms set forth in [`CLA.md`](CLA.md).

---

## 2. Development Setup

Allomorph strictly uses **`uv`** as its Python package and environment manager:

```bash
# Clone the repository
git clone https://github.com/pethin/allomorph.git
cd allomorph

# Install dependencies and sync environment
uv sync

# Run the automated test suite
uv run pytest
```

---

## 3. Engineering Guidelines & Guardrails

When writing code or adding netlists, please review and adhere to the project standards defined in [`AGENTS.md`](AGENTS.md) and [`docs/architectural_guardrails.md`](docs/architectural_guardrails.md):

* **Package & Dependencies:** Use `uv`. Strictly do not add `scipy`, `pandas`, `matplotlib`, or `soundfile`. Audio I/O is handled by `pedalboard`, dataframes by `polars`, and charts by `altair`.
* **Testing:** All pull requests must pass the test suite (`uv run pytest`) without regressions. New features, pickup profiles, or filter mathematics must include corresponding unit tests in `tests/`.
* **Code Style:** Keep Python code clean, vectorized with NumPy where appropriate, and formatted. Avoid interpreted Python loops over audio sample buffers (use Numba JIT `@njit(fastmath=True)` for iterative DSP state solvers).

---

## 4. Submitting a Pull Request

1. **Fork the repository** on GitHub.
2. **Create a topic branch** (`git checkout -b feat/my-new-pickup`).
3. **Write clean, tested code** and verify the test suite:
   ```bash
   uv run pytest
   ```
4. **Sign off your commits:**
   ```bash
   git commit -s -m "feat: description of changes"
   ```
5. **Open a Pull Request** against the `main` branch with a clear description of your changes and motivation.
