/**
 * Unmount whatever the previous test rendered.
 *
 * Testing Library registers this itself when vitest runs with `globals`, and
 * this project does not: imports are explicit everywhere else and the pure
 * suites are the better for it. Without the hook the DOM accumulates across a
 * file, so a test asserting an element is *absent* finds the one the previous
 * test rendered and fails describing a bug that is not there. That is a
 * misleading failure rather than a missing one, which is worse.
 */

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);
