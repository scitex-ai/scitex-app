import { gettext } from "@scitex/ui/src/scitex_ui/static/scitex_ui/ts/_base/gettext.ts";

export function Toolbar({ busy }: { busy: boolean }) {
  return <button title={gettext("Undo")}>{busy ? gettext("Saving…") : gettext("Save")}</button>;
}
