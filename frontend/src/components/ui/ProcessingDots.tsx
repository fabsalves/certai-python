/** Three staggered dots for a state that is genuinely in progress.
 *
 * Only use it where something is actually being watched -- a request in flight,
 * a polled status. On a state that will not change on its own the movement
 * promises liveness that is not there.
 *
 * Decoration: the surrounding block carries the accessible label. */
export function ProcessingDots() {
  return (
    <span className="processing-dots" aria-hidden>
      <span />
      <span />
      <span />
    </span>
  );
}
