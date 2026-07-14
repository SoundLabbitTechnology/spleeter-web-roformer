# Contributing

Thank you for your interest in contributing to this fork of Spleeter Web.

This repository is maintained by
[Sound Labbit Technology](https://www.soundlabbittechnology.co.jp/) and is
**not** the official upstream project. The upstream repository is
[JeffreyCA/spleeter-web](https://github.com/JeffreyCA/spleeter-web).

## Before you start

- Read [README.md](./README.md) for setup and the relationship with upstream.
- Follow the [Code of Conduct](./CODE_OF_CONDUCT.md).
- For changes that belong in the original project, consider opening a pull
  request against upstream instead of (or in addition to) this fork.

## How to contribute

1. Fork this repository and create a feature branch from `master`.
2. Keep changes focused and documented.
3. If you add a separation model or stem type, update both backend and frontend
   consistently (see `AGENTS.md`).
4. Open a pull request against
   `SoundLabbitTechnology/spleeter-web-roformer` with a clear description of
   the problem and the solution.

## Development notes

- Backend: Django / Celery / Redis
- Frontend: React 16 + TypeScript
- Prefer short audio files when manually testing separation jobs
- Do not commit secrets, `.env` files, or contents of `pretrained_models/`

## Security

Report vulnerabilities privately via [SECURITY.md](./SECURITY.md). Do not open
public issues for security problems.

## License

By contributing, you agree that your contributions will be licensed under the
same MIT License that covers this project. See [LICENSE](./LICENSE) and
[NOTICE](./NOTICE).
