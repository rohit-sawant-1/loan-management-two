// How an activity row is described in plain words.
//
// This lived inside the Activity page until the application detail page needed
// the same thing and was still printing raw stored data into a table cell. One
// copy, imported by both, so the two screens can never drift apart.

import { fieldList } from "./editRequests";
import { label, rupees, whole } from "./format";

// Plain words and an icon for each kind of event, instead of the stored name.
export const ACTIONS = {
  staff_registered:      { text: "Staff account created",    icon: "user" },
  applicant_signed_up:   { text: "Customer signed up",       icon: "user" },
  login_succeeded:       { text: "Signed in",                icon: "shield" },
  login_failed:          { text: "Sign-in failed",           icon: "alert" },
  applicant_created:     { text: "Borrower profile created", icon: "user" },
  application_submitted: { text: "Application submitted",    icon: "file" },
  status_changed:        { text: "Status changed",           icon: "activity" },
  document_added:        { text: "Document added",           icon: "file" },
  document_verified:     { text: "Document verified",        icon: "check" },
  eligibility_checked:   { text: "Eligibility checked",      icon: "shield" },
  dashboard_viewed:      { text: "Dashboard viewed",         icon: "dashboard" },
  // The assistant. `chat_action_confirmed` is the one a manager actually cares
  // about: it means someone told the AI to change a record and agreed to it.
  // Without these two here the rows still appeared, but with a raw stored name
  // and no way to filter for them — so "what has the AI been doing?" had no
  // answer on this screen.
  chat_message:          { text: "Asked the assistant",      icon: "activity" },
  chat_action_confirmed: { text: "Change made via assistant", icon: "shield" },
  chat_review:           { text: "Reviewed by the assistant", icon: "shield" },
  // Piece 25: a customer asking to change their application, and what came of it.
  edit_requested:        { text: "Edit requested",           icon: "file" },
  edit_request_approved: { text: "Edit request approved",    icon: "check" },
  edit_request_refused:  { text: "Edit request refused",     icon: "close" },
  application_edited:    { text: "Application edited",       icon: "refresh" },
  edit_request_closed:   { text: "Edit request closed",      icon: "info" },
  // Piece 28: the administrator changing a system setting.
  setting_changed:       { text: "Setting changed",          icon: "settings" },
  // Piece 31: a real file's bytes being opened (staff and admin views only;
  // the owner looking at their own document is not logged), and an upload
  // the safety pipeline refused before anything was stored.
  document_viewed:       { text: "Document viewed",          icon: "file" },
  upload_blocked:        { text: "Upload blocked",           icon: "alert" },
};

export const describe = (action) => ACTIONS[action] || { text: label(action), icon: "info" };

// Turn a stored detail key into something readable.
export const DETAIL_LABELS = {
  from: "Changed from", to: "Changed to", remarks: "Remarks", reason: "Reason",
  loan_type: "Loan type", amount: "Amount", tenure_months: "Tenure",
  doc_type: "Document type", file_name: "File name", application_id: "Application",
  // Piece 31. "reason" is already labelled above, and reads fine here too —
  // an upload_blocked row's reason is why it was refused, same idea.
  size_before: "Size before", size_after: "Size after", nature: "Classified as",
  eligible: "Passed eligibility", problem_count: "Rules not met", email: "Email",
  question: "Question asked (first 200 characters)", answer: "Answer given (first 500 characters)", tool: "What was done", worked: "Went through",
  outcome: "Result", new_status: "Changed to", mode: "Answered by",
  ai_status: "AI status", arguments: "Details", tools: "Steps taken",
  applicant_id: "Applicant", amount_requested: "Amount", purpose: "Purpose",
  sources: "Manual extracts used",
  // Piece 28. `key` is which setting changed; "from" and "to" are labelled above.
  key: "Setting",
  decision: "Verdict", risk_score: "Risk score", agents_run: "Agents that ran",
  compliance_passed: "Compliance passed", errors: "What went wrong",
  // Piece 25
  request_id: "Edit request number", fields: "Asked to change", note: "Staff note",
  eligibility_passed_before: "Passed eligibility before", eligibility_passed_after: "Passes eligibility now",
  previous_eligibility_summary: "Eligibility before the edit",
};

// The assistant's tools, in words someone auditing a bank would use. These are
// function names in the stored data — fine for a developer, meaningless in an
// audit trail that a branch manager is supposed to be able to read.
export const TOOL_NAMES = {
  update_application_status: "Changed an application's status",
  submit_loan_application:   "Created a new application",
  upload_document_metadata:  "Recorded a document",
  get_application_details:   "Looked up an application",
  list_applications:         "Searched the applications list",
  list_applications_by_filter: "Searched the applications list",
  get_dashboard_summary:     "Read the dashboard figures",
  get_applicant_details:     "Looked up an applicant",
  search_loan_policy:        "Read the user manual",
  // Phase 5's four agents, which report one message each per review.
  data_collector:            "Collected the application data",
  risk_assessor:             "Assessed the risk",
  compliance_checker:        "Checked compliance",
  decision_maker:            "Made the decision",
};

/** The stored details are a small piece of JSON. Hand back an object, or null. */
export function parseDetails(raw) {
  try {
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && Object.keys(parsed).length ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * One line summarising what changed, for a table cell where a full list would
 * not fit. "Under review → Approved", "Aadhaar.pdf", and so on.
 */
export function summarise(action, raw) {
  const d = parseDetails(raw);
  if (!d) return "";
  if (action === "status_changed" && d.to) {
    return d.from ? `${label(d.from)} → ${label(d.to)}` : label(d.to);
  }
  if (action === "application_submitted" && d.loan_type) {
    return `${label(d.loan_type)} loan`;
  }
  if ((action === "document_added" || action === "document_verified") && d.doc_type) {
    return label(d.doc_type);
  }
  if (action === "eligibility_checked") {
    return d.eligible ? "Passed" : `${d.problem_count ?? 0} rule(s) not met`;
  }
  // Whether the change actually went through is the whole point of this row.
  // A blocked one — an officer trying to disburse — must not look the same as
  // one that succeeded.
  if (action === "chat_action_confirmed") {
    const what = d.arguments?.new_status ? label(d.arguments.new_status) : "";
    const verdict = d.worked ? "Done" : "Refused";
    return what ? `${verdict} — ${what}` : verdict;
  }
  if (action === "chat_message" && d.question) {
    return d.question.length > 60 ? `${d.question.slice(0, 60)}…` : d.question;
  }
  // The verdict is the point of a review, so it goes in the table itself
  // rather than only in the panel behind "View".
  // Piece 25. The fields asked for, or for a save, the first change made.
  if ((action === "edit_requested" || action === "edit_request_approved") && d.fields) {
    return label(fieldList(d.fields));
  }
  if (action === "edit_request_refused" && d.note) {
    return d.note.length > 60 ? `${d.note.slice(0, 60)}…` : d.note;
  }
  if (action === "application_edited" && d.before && d.after) {
    const [field] = Object.keys(d.after);
    if (!field) return "";
    const show = (v) => (field === "amount_requested" ? rupees(v)
      : field === "tenure_months" ? `${v} months` : "new purpose");
    return field === "purpose" ? "Purpose changed" : `${show(d.before[field])} → ${show(d.after[field])}`;
  }
  if (action === "edit_request_closed") return "The application moved on";
  if (action === "chat_review") {
    if (d.errors?.length) return "Could not run";
    return d.risk_score != null
      ? `${label(d.decision)} · risk ${whole(d.risk_score)}/100`
      : label(d.decision);
  }
  return "";
}
