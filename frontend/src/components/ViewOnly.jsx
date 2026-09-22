// What the administrator sees where an action button would be (Piece 27).
// The admin can see every record but change none of them, and a button that
// just vanished would look like a bug, so the gap is labelled instead.

import Icon from "./ui/Icon";

export default function ViewOnly({ children = "View only" }) {
  return (
    <span className="view-only">
      <Icon name="info" size={14} />
      <span>{children}</span>
    </span>
  );
}
