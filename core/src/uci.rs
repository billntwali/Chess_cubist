/// UCI protocol loop. Reads from stdin, writes to stdout.
/// Spawns the Python eval server subprocess when --eval-server is provided.
use std::io::{self, BufRead, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::io::BufReader;

pub struct EvalServer {
    process: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

impl EvalServer {
    pub fn spawn(cmd: &str) -> Self {
        let mut parts = cmd.split_whitespace();
        let program = parts.next().expect("eval-server cmd is empty");
        let args: Vec<&str> = parts.collect();

        let mut child = Command::new(program)
            .args(&args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .expect("failed to spawn eval server");

        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        EvalServer { process: child, stdin, stdout }
    }

    /// Send a FEN, return the centipawn score. Returns 0 on error.
    pub fn eval(&mut self, fen: &str) -> i32 {
        writeln!(self.stdin, "{}", fen).unwrap();
        self.stdin.flush().unwrap();

        let mut line = String::new();
        self.stdout.read_line(&mut line).unwrap();
        let line = line.trim();

        if line.starts_with("ERR") {
            eprintln!("[eval-server] {}", line);
            return 0;
        }
        line.parse::<i32>().unwrap_or(0)
    }
}

impl Drop for EvalServer {
    fn drop(&mut self) {
        let _ = writeln!(self.stdin, "quit");
        let _ = self.process.wait();
    }
}

pub fn run() {
    let args: Vec<String> = std::env::args().collect();
    let eval_server_cmd = args.windows(2)
        .find(|w| w[0] == "--eval-server")
        .map(|w| w[1].clone());

    let mut eval_server = eval_server_cmd.map(|cmd| EvalServer::spawn(&cmd));

    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());

    for line in stdin.lock().lines() {
        let line = line.unwrap();
        let line = line.trim();

        match line {
            "uci" => {
                writeln!(out, "id name ChessForge").unwrap();
                writeln!(out, "id author Chess Cubist").unwrap();
                writeln!(out, "uciok").unwrap();
            }
            "isready" => {
                writeln!(out, "readyok").unwrap();
            }
            "ucinewgame" => {
                // TODO: clear transposition table
            }
            cmd if cmd.starts_with("position") => {
                // TODO: parse position and moves, update board state
            }
            cmd if cmd.starts_with("go") => {
                // TODO: parse time controls, start search
                // Placeholder: emit a dummy bestmove
                writeln!(out, "bestmove 0000").unwrap();
            }
            "quit" => break,
            _ => {}
        }
        out.flush().unwrap();
    }
}
