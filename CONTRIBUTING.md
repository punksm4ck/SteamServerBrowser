Contributing to Steam Server Browser

We maintain strict enterprise standards for all pull requests and feature implementations. By participating in this project, you agree to abide by our architectural principles.

Development Workflow

Fork the repository.

Create a feature branch (git checkout -b feature/AdvancedFiltering).

Commit your changes logically (git commit -m 'feat: implement advanced latency heuristic').

Push to the branch (git push origin feature/AdvancedFiltering).

Open a Pull Request targeting the main branch.

Architectural Guidelines

Strict Threading: Never execute blocking network requests on the main UI thread. All networking must occur within the designated AsyncServerScanner or a newly spawned QThread.

State Management: Inter-thread communication must strictly utilize pyqtSignal and pyqtSlot. Direct modification of GUI elements from background threads is strictly prohibited and will result in PR rejection.

FastDL Modifications: Any modifications to the FastDL interceptor must gracefully handle HTTP timeouts, 404s, and malformed bz2 archives without crashing the daemon.

Bug Reports

Submit detailed bug reports via GitHub Issues including:

OS/Environment specifications.

Stack trace (if applicable).

Steps to reproduce the error reliably.
