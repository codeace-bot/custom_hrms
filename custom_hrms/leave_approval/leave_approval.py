import frappe
from frappe.model.document import Document

class LeaveApproval(Document):
    def validate(self):
        """
        Prevent duplicate Leave Approval for same Leave Application
        """
        if self.is_new():
            if frappe.db.exists("Leave Approval", {"leave_application": self.leave_application}):
                frappe.throw("A Leave Approval already exists for this Leave Application.")

    def on_update(self):
        """
        Sync approval status and reason to Leave Application and log comment
        """
        if not self.leave_application:
            return

        try:
            if self.status == "Approved":
                frappe.db.set_value("Leave Application", self.leave_application, {
                    "team_lead_approval_status": "Approved",
                    "team_lead_rejection_reason": ""
                })
                self.add_comment("Comment", f"Team Lead ({self.team_lead}) approved the leave.")

            elif self.status == "Rejected":
                frappe.db.set_value("Leave Application", self.leave_application, {
                    "status": "Rejected",  # Reflect rejection in main status
                    "team_lead_approval_status": "Rejected",
                    "team_lead_rejection_reason": self.reason or ""
                })
                self.add_comment("Comment", f"Team Lead ({self.team_lead}) rejected the leave. Reason: {self.reason or 'Not provided'}")

            elif self.status == "Pending":
                frappe.db.set_value("Leave Application", self.leave_application, {
                    "team_lead_approval_status": "Pending",
                    "team_lead_rejection_reason": ""
                })

        except Exception:
            frappe.log_error(frappe.get_traceback(), "Leave Approval: Failed to sync with Leave Application")

def has_permission(doc, ptype, user):
    """
    Production-safe permission logic:
    - Allow System Manager (always)
    - Allow HR Manager (read-only)
    - Allow the User ID of the employee's Team Lead (via reports_to > user_id)
    """
    try:
        if not doc or not getattr(doc, "employee", None):
            frappe.log_error("Permission check failed: doc or employee missing", "Leave Approval - has_permission")
            return False

        if frappe.has_role(user, "System Manager"):
            return True

        if frappe.has_role(user, "HR Manager"):
            return ptype in ["read"]

        reports_to = frappe.db.get_value("Employee", doc.employee, "reports_to")
        if not reports_to:
            frappe.log_error(f"Employee '{doc.employee}' has no 'reports_to'", "Leave Approval - has_permission")
            return False

        team_lead_user = frappe.db.get_value("Employee", reports_to, "user_id")
        if not team_lead_user:
            frappe.log_error(f"'reports_to' employee '{reports_to}' has no 'user_id'", "Leave Approval - has_permission")
            return False

        if user == team_lead_user:
            return True

        frappe.log_error(
            f"Unauthorized access attempt by '{user}'. Expected Team Lead: '{team_lead_user}' for employee '{doc.employee}'",
            "Leave Approval - has_permission"
        )
        return False

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Leave Approval - has_permission: Exception")
        return False

