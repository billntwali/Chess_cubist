/// Transposition table using Zobrist hashing.
use shakmaty::zobrist::{Zobrist64, ZobristHash};
use shakmaty::Chess;

#[derive(Clone, Copy, PartialEq)]
pub enum NodeType {
    Exact,
    LowerBound, // alpha cutoff
    UpperBound, // beta cutoff
}

#[derive(Clone, Copy)]
pub struct TTEntry {
    pub key: u64,
    pub depth: u8,
    pub score: i32,
    pub node_type: NodeType,
}

pub struct TranspositionTable {
    entries: Vec<Option<TTEntry>>,
    size: usize,
}

impl TranspositionTable {
    pub fn new(size_mb: usize) -> Self {
        let entry_size = std::mem::size_of::<Option<TTEntry>>();
        let size = (size_mb * 1024 * 1024) / entry_size;
        TranspositionTable {
            entries: vec![None; size],
            size,
        }
    }

    pub fn probe(&self, pos: &Chess) -> Option<TTEntry> {
        let key = self.hash(pos);
        let idx = (key as usize) % self.size;
        self.entries[idx].filter(|e| e.key == key)
    }

    pub fn store(&mut self, pos: &Chess, depth: u8, score: i32, node_type: NodeType) {
        let key = self.hash(pos);
        let idx = (key as usize) % self.size;
        self.entries[idx] = Some(TTEntry { key, depth, score, node_type });
    }

    pub fn clear(&mut self) {
        self.entries.iter_mut().for_each(|e| *e = None);
    }

    fn hash(&self, pos: &Chess) -> u64 {
        pos.zobrist_hash::<Zobrist64>().0
    }
}
