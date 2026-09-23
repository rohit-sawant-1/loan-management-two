// Piece 32: an unmistakable mark on any document the server classified as
// TEST material (see StoredFile.nature on the backend). The server always
// sends `nature` — this component never guesses.

export default function TestBadge() {
  return (
    <span
      className="badge badge-test"
      title="TEST DOCUMENT — for demonstration only. Not a genuine customer document."
    >
      TEST
    </span>
  );
}
