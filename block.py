"""
Implementation from https://bitcoin.org/bitcoin.pdf

Focus on micropayments, non-reversiable transactions, removing 3rd party intermediary,
eliminate double-spend, public transactions, timestamp of transactions, proof-of-work
is one-CPU-one-vote, POW difficulty is determined by a moving average of blocks per hour.

Coin - "chain of digital signatures"
Chain - seq of hash(Block of items + prev hash). Longest chain wins. If CPU power controlled
  by honest nodes, the honest chain will grow fastest.
Proof of Work - Create value when hash that value starts with a number of zero bits.
  Average work required is exponential in the number of zero bits required, yet verified
  in a single hash
Block - Header(Prev hash, Nonce, root hash) transactions.
Network-
  * New txns broadcasted to all nodes
  * Each node collects txns in a block
  * Each node works on finding POW for block
  * POW block is broadcasted
  * Nodes accept block if all txns are validate
  * Nodes express acceptance of block by working on next block with prev hash
Incentive - First txn is a special new coin for creator of block. Can also be
funded with txn fees.
  * Provides incentive for supporting network
  * Adds new coins into circulation (analagous to gold miners expending resources
    to add gold into circulation)
  * Encourage honesty - more profitable to mine and get new coins than undermine the
    system
Merkle Tree - Prune txn hashes to remove non-ultimate txns
Verify Payments - Use blockchain headers, look at timestamp of block to find merkle tree.
  Confirm that it is accepted by node, and blocks are added after it.
Transactions - Contain multiple inputs and outputs. Normally 2 outputs: payment and change
  back to sender. Inputs combine smaller amounts >= cost.
Privacy - Txns are public, but public keys can be anonymous. Use new key pair for each txn
  to prevent linking.
 
"""
import hashlib
import json
import random
import time

MINING_COST = 1


def get_hash(dict_data):
    sha = hashlib.sha256()
    data = json.dumps(dict_data, sort_keys=True)
    # sha.update(str(data).encode('utf-8'))
    print(data)
    sha.update((data).encode("utf-8"))
    return sha.hexdigest()


class Amount:
    def __init__(self, uuid, amount):
        self.uuid = uuid
        self.amount = amount

    def __repr__(self):
        return f"Amount({self.uuid}, {self.amount})"

    def __eq__(self, other):
        return self.uuid == other.uuid and self.amount == other.amount

    def todict(self):
        return {"uuid": self.uuid, "amount": self.amount}

    @classmethod
    def fromdict(cls, d):
        return cls(**d)


class Transaction:
    def __init__(self, inputs, outputs, timestamp=None):
        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = timestamp or time.time()

    def __repr__(self):
        return f"Transaction({self.inputs}, {self.outputs})"

    def __eq__(self, other):
        return (
            self.inputs == other.inputs
            and self.outputs == other.outputs
            and self.timestamp == other.timestamp
        )

    def todict(self):
        return {
            "inputs": list([i.todict() for i in self.inputs]),
            "outputs": list([o.todict() for o in self.outputs]),
            "timestamp": self.timestamp,
        }

    @classmethod
    def fromdict(cls, d):
        ts = d["timestamp"]
        inputs = [Amount.fromdict(a) for a in d["inputs"]]
        outputs = [Amount.fromdict(a) for a in d["outputs"]]
        txn = cls(inputs, outputs, ts)
        return txn


class Block:
    def __init__(self, txns, prev_hash, difficulty):
        self.prev_hash = prev_hash
        self.txns = txns
        self.nonce = None
        self.difficulty = difficulty

    def __repr__(self):
        return f"Block({self.txns})"

    def __eq__(self, other):
        return self.prev_hash == other.prev_hash and self.txns == other.txns

    def dumps(self):
        """
        Return JSON representation
        """
        data = self.todict()
        return json.dumps(data, sort_keys=True)

    def todict(self, nonce=None):
        nonce = nonce if nonce is not None else self.nonce
        body = {"txns": list([t.todict() for t in self.txns])}
        data = {
            "header": {
                "prev_hash": self.prev_hash,
                "body_hash": get_hash(body),
                "difficulty": self.difficulty,
                "nonce": nonce,
            },
            "body": body,
        }
        return data

    @classmethod
    def fromdict(cls, d):
        prev_hash = d["header"]["prev_hash"]
        difficulty = d["header"]["difficulty"]
        txns = [Transaction.fromdict(x) for x in d["body"]["txns"]]
        b = cls(txns, prev_hash, difficulty)
        return b

    def get_hash(self, nonce):
        return get_hash(self.todict(nonce))


def to_db(db_con, blocks):

    cur = db_con.cursor()
    for b in blocks:
        data = b.dumps()
        cur.execute("INSERT INTO Blocks VALUES(0, '{}')".format(data))


def from_db(db_con):
    blocks = []
    cur = db_con.cursor()
    rows = cur.execute("SELECT * from Blocks").fetchall()
    for row in rows:
        blocks.append(Block.fromdict(json.loads(row[1])))
    return blocks


class Node:
    def __init__(self, uuid):
        self.uuid = uuid
        self.blocks = []

    def process_txns(self, txns, difficulty=1, timestamp=None):
        txns.insert(
            0, Transaction([], [Amount(self.uuid, MINING_COST)], timestamp=timestamp)
        )
        if self.blocks:
            prev_hash = self.blocks[-1].prev_hash
        else:
            prev_hash = ""
        block = Block(txns, prev_hash, difficulty)
        nonce = 0
        while True:
            hash = block.get_hash(nonce)
            if hash.startswith("0" * difficulty):
                block.nonce = nonce
                self.blocks.append(block)
                return block, hash
            nonce += 1


def validate_hash(block, hash):
    return block.get_hash(block.nonce) == hash


if __name__ == "__main__":
    # genesis block
    node = Node("matt")
    gb, hash = node.process_txns([])
    print(gb, gb.nonce)
    # pay fred .1
    txn = Transaction([Amount(1, "matt")], [Amount(0.9, "matt"), Amount(0.1, "fred")])
    b2, h2 = node.process_txns([txn])
    print(b2, b2.nonce)
