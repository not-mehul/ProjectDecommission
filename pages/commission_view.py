"""Commission screen.

Drives one of the predefined org-setup flows (ESS / VSSL / VSSE / AS /
ACS — see TEMPLATE_FIELDS in constants.py). The user picks a template
and a kit (assets/kits.csv), confirms the auto-filled device serials
and supporting users, then `_run_step` walks through site/building/
device creation against the internal API. Each step's success/failure
is rendered in the live progress panel on the right."""

import asyncio
import csv
import functools
import os

import flet as ft

import theme
from apis.external_api import VerkadaExternalAPIClient
from constants import (
    AS_ACCESS_LEVEL_NAME,
    AS_ADDRESS,
    AS_ALARM_ADDRESS,
    AS_BUILDING_NAME,
    AS_CONTROLLER_NAME,
    AS_DOME_NAME,
    AS_DOOR_NAME,
    AS_FLOORS,
    AS_KEYPAD_NAME,
    AS_PANEL_NAME,
    AS_SITE_NAME,
    ACSL_MFA_DOOR_SCHEDULE_NAME,
    ACSL_ACCESS_STATION_PRO_DOOR_NAME,
    ACSL_ACCESS_STATION_PRO_NAME,
    ACSL_BUILDING_NAME,
    ACSL_FLOORS,
    ACSL_ADDRESS,
    ACSL_SITE_NAME,
    BORDER,
    BUILDING_PROVISION_SECONDS,
    CARD_PADDING,
    CARD_SHADOW,
    ERROR,
    ESS_ADDRESS,
    ESS_ALARM_ADDRESS,
    ESS_BUILDING_NAME,
    ESS_CAMERA_NAME,
    ESS_FLOORS,
    ESS_GUEST_ADDRESS,
    ESS_PANEL_NAME,
    ESS_ACCESS_STATION_PRO_NAME,
    ESS_ACCESS_STATION_PRO_DOOR_NAME,
    ESS_SITE_NAME,
    FIELD_SPACING,
    HQ_TIMEZONE,
    LICENSE_PLATE_FIELD,
    PRIMARY,
    ROLE_PROPAGATION_SECONDS,
    SECONDARY,
    SURFACE,
    TEMPLATE_DISPLAY_NAMES,
    TEMPLATE_FIELDS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VSS_ACCESS_GROUP_NAME,
    VSS_ACCESS_LEVEL_NAME,
    VSS_ADDRESS,
    VSS_BUILDING_NAME,
    VSS_BULLET_NAME,
    VSS_CONNECTOR_NAME,
    VSS_CONTROLLER_NAME,
    VSS_DOOR_NAME,
    VSS_EXAM_BULLET_NAME,
    VSS_EXAM_DOME_NAME,
    VSS_EXAM_FISHEYE_NAME,
    VSS_EXAM_SITE_NAME,
    VSS_FLOORS,
    VSS_PTZ_NAME,
    VSS_SITE_NAME,
    WARNING,
)
from components import (
    ProgressHeader,
    RawLogPanel,
    Stepper,
    banner,
    ghost_button,
    section_header,
    status_row,
    stat_row,
)
from pages.app_shell import ToolView
from utils.cancellation import CancellationToken
from utils.executor import _executor
from utils.export import export_csv
from utils.session import get_internal_client, set_external_client
from utils.ui_utils import show_alert, show_toast
from utils.validation import (
    SERIAL_DISPLAY_LEN,
    SERIAL_PLACEHOLDER,
    format_serial,
    is_valid_serial,
)

_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)

_COMMISSION_STEPS = ["Configure", "Review", "Run", "Report"]


class CommissionView(ToolView):
    def __init__(self, push_route, pop_route):
        super().__init__(
            push_route,
            pop_route,
            route="/commission",
            title="Commission Organization",
        )
        self._kits: dict[str, dict[str, str]] = {}
        self._device_fields: dict[str, ft.TextField] = {}
        # Cooperative cancel for the commission step loop. Checked
        # between steps; the in-flight step is allowed to complete.
        self._cancel_token: CancellationToken | None = None
        # Run tracking for the structured progress/report screen.
        self._steps_done = 0
        self._steps_failed = 0
        self._failures: list[tuple[str, str]] = []
        self._run_log: list[str] = []
        self._load_kits()
        self._build_ui()

    # ------------------------------------------------------------------
    # CSV / data loading
    # ------------------------------------------------------------------

    def _load_kits(self):
        internal = os.path.join(_ASSETS_DIR, "kits.internal.csv")
        public = os.path.join(_ASSETS_DIR, "kits.csv")
        path = internal if os.path.exists(internal) else public
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                kit_name = r["Kit Name"]
                if kit_name not in self._kits:
                    self._kits[kit_name] = {}
                self._kits[kit_name][r["Device Type"]] = r["Serial Number"]

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        template_options = [
            ft.dropdown.Option(key=code, text=TEMPLATE_DISPLAY_NAMES[code])
            for code in TEMPLATE_FIELDS
        ]
        self.template_dropdown = ft.Dropdown(
            label="Template",
            options=template_options,
            expand=1,
            border_color=BORDER,
            focused_border_color=PRIMARY,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            on_select=self._on_template_change,
        )

        kit_options = [ft.dropdown.Option("")] + [
            ft.dropdown.Option(k) for k in self._kits
        ]
        self.kit_dropdown = ft.Dropdown(
            label="Kit",
            options=kit_options,
            expand=1,
            border_color=BORDER,
            focused_border_color=PRIMARY,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            on_select=self._on_kit_change,
        )

        self._devices_column = ft.Column(spacing=FIELD_SPACING)

        self.face_analytics_switch = ft.Switch(
            label=" Face Analytics",
            value=True,
            active_color=PRIMARY,
            label_text_style=ft.TextStyle(color=TEXT_PRIMARY),
            visible=False,
        )

        self._users_column = ft.Column(spacing=10)
        add_user_btn = ft.TextButton(
            content=ft.Text("+ Add Supporting User", color=PRIMARY),
            on_click=self._add_user_row,
        )

        # Configure-step primary action advances to the Review summary
        # rather than running immediately.
        self.commission_btn = ft.ElevatedButton(
            content=ft.Text(
                "Review",
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_600,
            ),
            bgcolor=PRIMARY,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            height=45,
            on_click=self._on_review,
            expand=True,
        )
        # Cancel is shown during the Run step (next to the live progress),
        # hidden otherwise.
        self.cancel_btn = ft.OutlinedButton(
            content=ft.Text("Cancel", color=ERROR, weight=ft.FontWeight.W_500),
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, ERROR),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            height=45,
            on_click=self._on_cancel,
            visible=False,
        )
        self._button_row = ft.Row([self.commission_btn], spacing=10)

        self._progress_column = ft.Column(spacing=8, visible=False)

        self._form_section = ft.Column(
            [
                ft.Row(
                    [self.template_dropdown, self.kit_dropdown],
                    spacing=FIELD_SPACING,
                ),
                ft.Container(height=4),
                self._devices_column,
                self.face_analytics_switch,
                ft.Divider(color=BORDER, height=1),
                ft.Text(
                    "Supporting Users",
                    size=14,
                    color=TEXT_SECONDARY,
                    weight=ft.FontWeight.W_500,
                ),
                self._users_column,
                add_user_btn,
                ft.Container(height=8),
                self._button_row,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=FIELD_SPACING,
        )

        # Configure -> Review -> Run -> Report stepper, plus the Review and
        # Run panels (hidden until their step). The form_section is the
        # Configure step; _progress_column is the Run/Report step.
        self._stepper = Stepper(_COMMISSION_STEPS, current=0)
        self._review_section = ft.Column(
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=FIELD_SPACING,
        )
        # Total commission steps aren't known up front (flows branch by
        # template), so the run bar is indeterminate and reports live counts.
        self._progress_header = ProgressHeader(determinate=False)
        self._run_section = ft.Column(
            [
                self._progress_header,
                ft.Row([self.cancel_btn]),
                self._progress_column,
            ],
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=FIELD_SPACING,
        )

        form_card = ft.Container(
            bgcolor=SURFACE,
            border_radius=12,
            border=ft.Border.all(1, BORDER),
            shadow=CARD_SHADOW,
            padding=ft.Padding.all(CARD_PADDING),
            content=ft.Column(
                [
                    ft.Container(
                        content=self._stepper,
                        padding=ft.Padding.only(bottom=FIELD_SPACING),
                    ),
                    self._form_section,
                    self._review_section,
                    self._run_section,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                scroll=ft.ScrollMode.ADAPTIVE,
                spacing=FIELD_SPACING,
            ),
            expand=True,
        )

        self.mount(form_card)

    def _make_device_field(self, device_type: str, expand=None) -> ft.TextField:
        # License Plate holds a plate string rather than a device serial, so
        # it keeps a plain free-text field — no mask, no length cap.
        is_serial = device_type != LICENSE_PLATE_FIELD
        field = ft.TextField(
            label=f"{device_type} S/N" if is_serial else device_type,
            border_color=BORDER,
            focused_border_color=PRIMARY,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            expand=expand,
            hint_text=SERIAL_PLACEHOLDER if is_serial else None,
            max_length=SERIAL_DISPLAY_LEN if is_serial else None,
            on_change=self._on_serial_change if is_serial else None,
        )
        self._device_fields[device_type] = field
        return field

    def _on_serial_change(self, e) -> None:
        """
        Re-apply the serial mask on every keystroke so the field can only
        ever hold well-formed input: upper-cased, separators inserted, and
        anything else dropped as it is typed.
        """
        field = e.control
        masked = format_serial(field.value)
        if masked != field.value:
            field.value = masked
            e.page.update()

    # ------------------------------------------------------------------
    # Form event handlers
    # ------------------------------------------------------------------

    def _on_template_change(self, e):
        code = self.template_dropdown.value
        if not code or code not in TEMPLATE_FIELDS:
            self._devices_column.controls.clear()
            self.face_analytics_switch.visible = False
            e.page.update()
            return

        config = TEMPLATE_FIELDS[code]
        self._device_fields.clear()
        devices = config["devices"]
        rows = []
        for i in range(0, len(devices), 2):
            pair = devices[i : i + 2]
            row_fields: list[ft.Control] = [
                self._make_device_field(d, expand=1) for d in pair
            ]
            rows.append(ft.Row(row_fields, spacing=FIELD_SPACING))
        self._devices_column.controls = rows
        self.face_analytics_switch.visible = config["face_analytics"]
        self.face_analytics_switch.value = config["face_analytics"]

        if self.kit_dropdown.value:
            self._fill_from_kit(self.kit_dropdown.value)

        e.page.update()

    def _on_kit_change(self, e):
        kit_name = self.kit_dropdown.value
        if kit_name:
            self._fill_from_kit(kit_name)
        else:
            for field in self._device_fields.values():
                field.value = ""
        e.page.update()

    def _fill_from_kit(self, kit_name: str):
        kit_data = self._kits.get(kit_name, {})
        for device_type, field in self._device_fields.items():
            value = kit_data.get(device_type, "")
            # Kit values go through the same mask, so a serial field always
            # shows what typing the same characters would have produced.
            field.value = (
                value if device_type == LICENSE_PLATE_FIELD else format_serial(value)
            )

    def _add_user_row(self, e):
        row = self._create_user_row()
        self._users_column.controls.append(row)
        e.page.update()

    def _create_user_row(self) -> ft.Row:
        first = ft.TextField(
            label="First Name",
            border_color=BORDER,
            focused_border_color=PRIMARY,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            expand=1,
        )
        last = ft.TextField(
            label="Last Name",
            border_color=BORDER,
            focused_border_color=PRIMARY,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            expand=1,
        )
        email = ft.TextField(
            label="Email",
            border_color=BORDER,
            focused_border_color=PRIMARY,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            expand=2,
        )

        row = ft.Row(spacing=10)
        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ERROR,
            on_click=lambda _, r=row: self._remove_user_row(r),
        )
        row.controls = [first, last, email, delete_btn]
        return row

    def _remove_user_row(self, row):
        if row in self._users_column.controls:
            self._users_column.controls.remove(row)
            page = getattr(self, "page", None)
            if page:
                page.update()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _device_serial(self, device_type: str) -> str:
        """Return the trimmed value of a device field, '' if missing/empty."""
        field = self._device_fields.get(device_type)
        return (field.value or "").strip() if field else ""

    def _validate_form(self, e) -> tuple[bool, str | None]:
        """
        Returns (ok, code). When ok is False, an alert has already been shown.
        When ok is True, code is the selected template code.
        """
        code = self.template_dropdown.value
        if not code or code not in TEMPLATE_FIELDS:
            show_toast(e.page, "Please select a template.", kind="warning")
            return False, None

        config = TEMPLATE_FIELDS[code]
        for device_type in config["devices"]:
            value = self._device_serial(device_type)
            is_serial = device_type != LICENSE_PLATE_FIELD
            if not value:
                show_toast(
                    e.page,
                    f"Please enter the {device_type} serial number."
                    if is_serial
                    else f"Please enter the {device_type}.",
                    kind="warning",
                )
                return False, None
            # The mask keeps the field well-formed while typing; this
            # catches the half-typed case (e.g. "A1A1-B2") on submit.
            if is_serial and not is_valid_serial(value):
                show_toast(
                    e.page,
                    f"{device_type} serial number must look like "
                    f"{SERIAL_PLACEHOLDER}.",
                    kind="warning",
                )
                return False, None

        return True, code

    # ------------------------------------------------------------------
    # Review step
    # ------------------------------------------------------------------

    def _collect_supporting_users(self) -> list[tuple[str, str, str]]:
        """Pull (first, last, email) tuples from the non-empty user rows."""
        users: list[tuple[str, str, str]] = []
        for row in self._users_column.controls:
            if isinstance(row, ft.Row) and len(row.controls) >= 3:
                first = (row.controls[0].value or "").strip()
                last = (row.controls[1].value or "").strip()
                email = (row.controls[2].value or "").strip()
                if first or last or email:
                    users.append((first, last, email))
        return users

    def _on_review(self, e):
        """Configure -> Review: validate, then show the pre-flight summary."""
        ok, code = self._validate_form(e)
        if not ok:
            return
        self._review_section.controls = self._build_review_summary(code)
        self._stepper.set_active(1)
        self._form_section.visible = False
        self._review_section.visible = True
        self._run_section.visible = False
        e.page.update()

    def _on_edit(self, e):
        """Review -> Configure: go back to editing the form."""
        self._stepper.set_active(0)
        self._form_section.visible = True
        self._review_section.visible = False
        e.page.update()

    def _build_review_summary(self, code: str) -> list[ft.Control]:
        """Build the Review panel: what will be created + Edit/Confirm."""
        config = TEMPLATE_FIELDS[code]
        rows: list[ft.Control] = [
            stat_row("Template", TEMPLATE_DISPLAY_NAMES.get(code, code)),
            stat_row("Kit", (self.kit_dropdown.value or "").strip() or "—"),
        ]
        for device_type in config["devices"]:
            rows.append(
                stat_row(device_type, self._device_serial(device_type) or "—")
            )
        if config.get("face_analytics"):
            rows.append(
                stat_row(
                    "Face Analytics",
                    "On" if self.face_analytics_switch.value else "Off",
                )
            )
        users = self._collect_supporting_users()
        rows.append(stat_row("Supporting Users", len(users)))
        for first, last, email in users:
            rows.append(
                ft.Text(
                    f"   • {first} {last}  ·  {email}".rstrip(),
                    size=12,
                    color=TEXT_SECONDARY,
                )
            )

        inset = ft.Container(
            bgcolor=theme.SURFACE_VARIANT,
            border=ft.Border.all(1, BORDER),
            border_radius=theme.RADIUS_MD,
            padding=ft.Padding.all(CARD_PADDING),
            content=ft.Column(rows, spacing=theme.SPACE_SM),
        )

        confirm_btn = ft.ElevatedButton(
            content=ft.Text(
                "Commission Organization",
                color=TEXT_PRIMARY,
                weight=ft.FontWeight.W_600,
            ),
            bgcolor=PRIMARY,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            height=45,
            on_click=self._on_commission,
            expand=True,
        )

        return [
            section_header(
                "Review", "Confirm what will be created before commissioning."
            ),
            inset,
            ft.Row(
                [
                    ghost_button(
                        "Edit", on_click=self._on_edit, icon=ft.Icons.ARROW_BACK
                    ),
                    confirm_btn,
                ],
                spacing=10,
            ),
        ]

    # ------------------------------------------------------------------
    # Commission orchestration
    # ------------------------------------------------------------------

    async def _on_commission(self, e):
        ok, code = self._validate_form(e)
        if not ok:
            return

        # Review -> Run: swap panels, advance the stepper, arm cancellation.
        self._stepper.set_active(2)
        self._form_section.visible = False
        self._review_section.visible = False
        self._run_section.visible = True
        self._progress_column.controls.clear()
        self._progress_column.visible = True
        # Reset run tracking for the structured progress header / report.
        self._steps_done = 0
        self._steps_failed = 0
        self._failures = []
        self._run_log = []
        self._progress_header.set_progress(0, failed=0)
        self._cancel_token = CancellationToken()
        self.cancel_btn.visible = True
        self.cancel_btn.disabled = False
        if isinstance(self.cancel_btn.content, ft.Text):
            self.cancel_btn.content.value = "Cancel"
        e.page.update()
        await asyncio.sleep(0)

        client = get_internal_client()
        loop = asyncio.get_running_loop()

        api_key = await loop.run_in_executor(_executor, client.create_external_api_key)
        ext_client = await loop.run_in_executor(
            _executor,
            VerkadaExternalAPIClient,
            api_key,
            client.org_short_name,
        )
        set_external_client(ext_client)

        page = e.page

        async def step(label: str, fn, *args) -> tuple[bool, object]:
            return await self._run_step(page, loop, label, fn, *args)

        all_success = True

        def track(ok_value: bool) -> None:
            nonlocal all_success
            all_success = ok_value and all_success

        # ── Common prelude ──
        if code in ("ESS", "ACSL", "ACSE", "VSSL", "VSSE", "AS"):
            ok, _ = await step("Enabling custom roles", client.enable_custom_roles)
            track(ok)
            self._progress_note(page, "Waiting for roles to propagate...")
            await asyncio.sleep(ROLE_PROPAGATION_SECONDS)
            ok, _ = await step(
                "Disabling global site admin", client.disable_global_site_admin
            )
            track(ok)

        # ── Per-template flows ──
        if code == "ESS":
            await self._run_ess_flow(step, track, page, client)
        elif code == "ACSL":
            await self._run_acsl_flow(step, track, page, client)
        elif code == "ACSE":
            # No additional steps beyond the prelude.
            pass
        elif code == "VSSL":
            await self._run_vssl_flow(step, track, page, client, ext_client)
        elif code == "VSSE":
            await self._run_vsse_flow(step, track, page, client)
        elif code == "AS":
            await self._run_as_flow(step, track, page, client)

        # ── Supporting users — shared across all templates ──
        user_role = "Org Admin"
        await self._invite_supporting_users(step, track, client, user_role)

        # ── Final summary card ──
        self._render_summary(page, all_success)

    # ------------------------------------------------------------------
    # Per-template flows
    # ------------------------------------------------------------------

    async def _run_ess_flow(self, step, track, page, client) -> None:
        dome_serial = self._device_serial("Dome")
        panel_serial = self._device_serial("Alarm Panel")
        access_station_pro_serial = self._device_serial("Access Station Pro")

        ok, site_id = await step("Creating site", client.create_site, ESS_SITE_NAME)
        track(ok)

        ok, camera_id = await step(
            f"Adding camera ({dome_serial})",
            client.add_device,
            ESS_CAMERA_NAME,
            dome_serial,
        )
        track(ok)

        ok, panel_id = await step(
            f"Adding alarm panel ({panel_serial})",
            client.add_device,
            ESS_PANEL_NAME,
            panel_serial,
        )
        track(ok)

        ok, access_station_pro_id = await step(
            f"Adding access station pro ({access_station_pro_serial})",
            client.add_device,
            ESS_ACCESS_STATION_PRO_NAME,
            access_station_pro_serial,
        )
        track(ok)

        ok, floor_id = await step(
            "Creating building",
            client.create_building,
            ESS_BUILDING_NAME,
            ESS_ADDRESS,
            ESS_FLOORS,
        )
        track(ok)

        self._progress_note(page, "Waiting for building to provision...")
        await asyncio.sleep(BUILDING_PROVISION_SECONDS)

        if camera_id and site_id:
            ok, _ = await step(
                "Configuring camera",
                client.configure_camera,
                camera_id,
                ESS_CAMERA_NAME,
                site_id,
                ESS_ADDRESS,
            )
            track(ok)

        ok, _ = await step(
            "Enabling org features",
            client.enable_org_features,
            self.face_analytics_switch.value,
        )
        track(ok)

        ok, _ = await step(
            "Enabling org face unlock",
            client.enable_org_face_unlock,
        )
        track(ok)

        if self.face_analytics_switch.value and camera_id:
            ok, _ = await step(
                "Enabling camera analytics",
                client.enable_camera_analytics,
                [camera_id],
            )
            track(ok)

        if site_id:
            ok, alarm_response_id = await step(
                "Creating alarm site",
                client.create_alarm_site,
                "Verkada",
                ESS_ALARM_ADDRESS,
                site_id,
            )
            track(ok)

            if alarm_response_id:
                ok, _ = await step(
                    "Setting response to Self-Monitored",
                    client.set_alarm_self_monitored,
                    site_id,
                    alarm_response_id,
                )
                track(ok)

            ok, _ = await step(
                "Creating guest site",
                client.create_guest_site,
                ESS_GUEST_ADDRESS,
                site_id,
            )
            track(ok)

        if panel_id and site_id:
            ok, alarm_system_id = await step(
                "Creating alarm system",
                client.create_alarm_system,
                site_id,
            )
            track(ok)
            if alarm_system_id:
                ok, _ = await step(
                    "Configuring alarm panel",
                    client.configure_alarm_panel,
                    panel_id,
                    ESS_PANEL_NAME,
                    alarm_system_id,
                )
                track(ok)

        if access_station_pro_id and site_id:
            ok, access_station_pro_controller_id = await step(
                "Configuring Access Station Pro",
                client.configure_access_station_pro,
                access_station_pro_id,
                ESS_ACCESS_STATION_PRO_NAME,
                site_id,
                ESS_ADDRESS
            )
            track(ok)

            door_id = None
            if access_station_pro_controller_id:
                ok, door_id = await step(
                    "Creating door",
                    client.create_access_station_pro_door,
                    access_station_pro_controller_id,
                    ESS_ACCESS_STATION_PRO_DOOR_NAME,
                    floor_id,
                )
                track(ok)

            if door_id and access_station_pro_controller_id:
                ok, _ = await step(
                    "Enabling Face Unlock on Door",
                    client.enable_door_face_unlock,
                    door_id,
                )
                track(ok)

    async def _run_acsl_flow(self, step, track, page, client) -> None:
        access_station_pro_serial = self._device_serial("Access Station Pro")

        ok, site_id = await step("Creating site", client.create_site, ACSL_SITE_NAME)
        track(ok)

        ok, access_station_pro_id = await step(
            f"Adding access station pro ({access_station_pro_serial})",
            client.add_device,
            ACSL_ACCESS_STATION_PRO_NAME,
            access_station_pro_serial,
        )
        track(ok)

        ok, floor_id = await step(
            "Creating building",
            client.create_building,
            ACSL_BUILDING_NAME,
            ACSL_ADDRESS,
            ACSL_FLOORS,
        )
        track(ok)

        ok, _ = await step(
            "Enabling org face unlock",
            client.enable_org_face_unlock,
        )
        track(ok)

        if access_station_pro_id and site_id:
            ok, access_station_pro_controller_id = await step(
                "Configuring Access Station Pro",
                client.configure_access_station_pro,
                access_station_pro_id,
                ACSL_ACCESS_STATION_PRO_NAME,
                site_id,
                ACSL_ADDRESS
            )
            track(ok)
            door_id = None
            if access_station_pro_controller_id:
                ok, door_id = await step(
                    "Creating door",
                    client.create_access_station_pro_door,
                    access_station_pro_controller_id,
                    ACSL_ACCESS_STATION_PRO_DOOR_NAME,
                    floor_id,
                )
                track(ok)

            if door_id and access_station_pro_controller_id:
                ok, _ = await step(
                    "Enabling Face Unlock on Door",
                    client.enable_door_face_unlock,
                    door_id,
                )
                track(ok)

                ok, _ = await step(
                    "Enabling Card + Code",
                    client.enable_door_mfa_card_code,
                    door_id,
                )
                track(ok)

                ok, _ = await step(
                    "Enabling Face + Card",
                    client.enable_door_mfa_face_card,
                    door_id,
                )
                track(ok)

                ok, _ = await step(
                    "Enabling Face + Code",
                    client.enable_door_mfa_face_code,
                    door_id,
                )
                track(ok)

                ok, _ = await step(
                    "Creating MFA Door Schedule",
                    client.create_mfa_schedule,
                    door_id,
                    ACSL_MFA_DOOR_SCHEDULE_NAME,
                )
                track(ok)

    async def _run_vssl_flow(self, step, track, page, client, ext_client) -> None:
        bullet_serial = self._device_serial("Bullet")
        ptz_serial = self._device_serial("PTZ")
        connector_serial = self._device_serial("Command Connector")
        controller_serial = self._device_serial("Access Controller")
        license_plate = self._device_serial("License Plate")

        ok, site_id = await step("Creating site", client.create_site, VSS_SITE_NAME)
        track(ok)

        ok, bullet_id = await step(
            f"Adding camera ({bullet_serial})",
            client.add_device,
            VSS_BULLET_NAME,
            bullet_serial,
        )
        track(ok)

        ok, ptz_id = await step(
            f"Adding PTZ ({ptz_serial})",
            client.add_device,
            VSS_PTZ_NAME,
            ptz_serial,
        )
        track(ok)

        ok, connector_id = await step(
            f"Adding command connector ({connector_serial})",
            client.add_device,
            VSS_CONNECTOR_NAME,
            connector_serial,
        )
        track(ok)

        ok, controller_id = await step(
            f"Adding access controller ({controller_serial})",
            client.add_device,
            VSS_CONTROLLER_NAME,
            controller_serial,
        )
        track(ok)

        ok, floor_id = await step(
            "Creating building",
            client.create_building,
            VSS_BUILDING_NAME,
            VSS_ADDRESS,
            VSS_FLOORS,
        )
        track(ok)

        self._progress_note(page, "Waiting for building to provision...")
        await asyncio.sleep(BUILDING_PROVISION_SECONDS)

        if bullet_id and site_id:
            ok, _ = await step(
                "Configuring bullet",
                client.configure_camera,
                bullet_id,
                VSS_BULLET_NAME,
                site_id,
                VSS_ADDRESS,
            )
            track(ok)

        if ptz_id and site_id:
            ok, _ = await step(
                "Configuring PTZ",
                client.configure_camera,
                ptz_id,
                VSS_PTZ_NAME,
                site_id,
                VSS_ADDRESS,
            )
            track(ok)

        if connector_id and site_id:
            ok, _ = await step(
                "Configuring connector",
                client.configure_connector,
                connector_id,
                VSS_CONNECTOR_NAME,
                site_id,
                VSS_ADDRESS,
            )
            track(ok)

        door_id = None
        if controller_id and site_id:
            ok, access_controller_id = await step(
                "Configuring access controller",
                client.configure_access_controller,
                controller_id,
                VSS_CONTROLLER_NAME,
                site_id,
                floor_id,
                HQ_TIMEZONE,
            )
            track(ok)
            if access_controller_id:
                # LPR door: created with the LPR config up front (v2 has no
                # retroactive flag-flip), then the camera is paired below.
                ok, door_id = await step(
                    "Creating door",
                    functools.partial(
                        client.create_door,
                        access_controller_id,
                        VSS_DOOR_NAME,
                        floor_id,
                        lpr=True,
                    ),
                )
                track(ok)

        ok, _ = await step(
            "Enabling org features",
            client.enable_org_features,
            self.face_analytics_switch.value,
        )
        track(ok)

        if self.face_analytics_switch.value and ptz_id:
            ok, _ = await step(
                "Enabling camera analytics",
                client.enable_camera_analytics,
                [ptz_id],
            )
            track(ok)

        if bullet_id:
            ok, _ = await step(
                "Enabling LPR mode",
                client.enable_camera_lpr,
                [bullet_id],
            )
            track(ok)

        if ptz_id:
            ok, _ = await step(
                "Disabling PTZ Installation Mode",
                client.disable_camera_install_mode,
                [ptz_id],
            )
            track(ok)

        if door_id and bullet_id:
            ok, _ = await step(
                "Linking LPR camera to door",
                client.pair_lpr_camera,
                door_id,
                bullet_id,
            )
            track(ok)

        ok, group_id = await step(
            "Creating Access Group",
            ext_client.create_access_group,
            VSS_ACCESS_GROUP_NAME,
        )
        track(ok)

        ok, _ = await step(
            "Adding User to Access Group",
            ext_client.add_user_to_access_group,
            client.user_id,
            group_id,
        )
        track(ok)

        ok, _ = await step(
            "Adding License Plate to Access User",
            ext_client.add_license_plate_to_user,
            client.user_id,
            license_plate,
        )
        track(ok)

        if door_id:
            ok, _ = await step(
                "Creating Access Level",
                client.create_access_level,
                door_id,
                VSS_ACCESS_LEVEL_NAME,
                site_id,
                group_id,
            )
            track(ok)

    async def _run_vsse_flow(self, step, track, page, client) -> None:
        dome_serial = self._device_serial("Dome")
        fisheye_serial = self._device_serial("Fisheye")
        bullet_serial = self._device_serial("Bullet")

        ok, site_id = await step(
            "Creating site", client.create_site, VSS_EXAM_SITE_NAME
        )
        track(ok)

        ok, dome_id = await step(
            f"Adding dome ({dome_serial})",
            client.add_device,
            VSS_EXAM_DOME_NAME,
            dome_serial,
        )
        track(ok)

        ok, bullet_id = await step(
            f"Adding bullet ({bullet_serial})",
            client.add_device,
            VSS_EXAM_BULLET_NAME,
            bullet_serial,
        )
        track(ok)

        ok, fisheye_id = await step(
            f"Adding fisheye ({fisheye_serial})",
            client.add_device,
            VSS_EXAM_FISHEYE_NAME,
            fisheye_serial,
        )
        track(ok)

        for cam_id, cam_name in (
            (dome_id, VSS_EXAM_DOME_NAME),
            (fisheye_id, VSS_EXAM_FISHEYE_NAME),
            (bullet_id, VSS_EXAM_BULLET_NAME),
        ):
            if cam_id and site_id:
                ok, _ = await step(
                    f"Configuring {cam_name.lower()}",
                    client.configure_camera,
                    cam_id,
                    cam_name,
                    site_id,
                    VSS_ADDRESS,
                )
                track(ok)

        ok, _ = await step(
            "Enabling org features",
            client.enable_org_features,
            self.face_analytics_switch.value,
        )
        track(ok)

        if self.face_analytics_switch.value and (dome_id or fisheye_id):
            cams = [c for c in (dome_id, fisheye_id) if c]
            ok, _ = await step(
                "Enabling camera analytics",
                client.enable_camera_analytics,
                cams,
            )
            track(ok)

        if bullet_id:
            ok, _ = await step(
                "Enabling LPR mode",
                client.enable_camera_lpr,
                [bullet_id],
            )
            track(ok)

    async def _run_as_flow(self, step, track, page, client) -> None:
        dome_serial = self._device_serial("Dome")
        controller_serial = self._device_serial("Access Controller")
        panel_serial = self._device_serial("Alarm Panel")
        keypad_serial = self._device_serial("Keypad")

        ok, site_id = await step("Creating site", client.create_site, AS_SITE_NAME)
        track(ok)

        ok, dome_id = await step(
            f"Adding camera ({dome_serial})",
            client.add_device,
            AS_DOME_NAME,
            dome_serial,
        )
        track(ok)

        ok, controller_id = await step(
            f"Adding access controller ({controller_serial})",
            client.add_device,
            AS_CONTROLLER_NAME,
            controller_serial,
        )
        track(ok)

        ok, panel_id = await step(
            f"Adding alarm panel ({panel_serial})",
            client.add_device,
            AS_PANEL_NAME,
            panel_serial,
        )
        track(ok)

        ok, keypad_id = await step(
            f"Adding alarm keypad ({keypad_serial})",
            client.add_device,
            AS_KEYPAD_NAME,
            keypad_serial,
        )
        track(ok)

        ok, floor_id = await step(
            "Creating building",
            client.create_building,
            AS_BUILDING_NAME,
            AS_ADDRESS,
            AS_FLOORS,
        )
        track(ok)

        self._progress_note(page, "Waiting for building to provision...")
        await asyncio.sleep(BUILDING_PROVISION_SECONDS)

        door_id = None
        if controller_id and site_id:
            ok, access_controller_id = await step(
                "Configuring access controller",
                client.configure_access_controller,
                controller_id,
                AS_CONTROLLER_NAME,
                site_id,
                floor_id,
                HQ_TIMEZONE,
            )
            track(ok)
            if access_controller_id:
                ok, door_id = await step(
                    "Creating door",
                    client.create_door,
                    access_controller_id,
                    AS_DOOR_NAME,
                    floor_id,
                )
                track(ok)

        if door_id:
            ok, _ = await step(
                "Creating Access Level",
                client.create_access_level,
                door_id,
                AS_ACCESS_LEVEL_NAME,
                site_id,
                "",
            )
            track(ok)

        if dome_id and site_id:
            ok, _ = await step(
                "Configuring camera",
                client.configure_camera,
                dome_id,
                AS_DOME_NAME,
                site_id,
                AS_ADDRESS,
            )
            track(ok)

        ok, _ = await step(
            "Enabling org features",
            client.enable_org_features,
            self.face_analytics_switch.value,
        )
        track(ok)

        if self.face_analytics_switch.value and dome_id:
            ok, _ = await step(
                "Enabling camera analytics",
                client.enable_camera_analytics,
                [dome_id],
            )
            track(ok)

        if site_id:
            ok, alarm_response_id = await step(
                "Creating alarm site",
                client.create_alarm_site,
                "Verkada",
                AS_ALARM_ADDRESS,
                site_id,
            )
            track(ok)

            if alarm_response_id:
                ok, _ = await step(
                    "Setting response to Self-Monitored",
                    client.set_alarm_self_monitored,
                    site_id,
                    alarm_response_id,
                )
                track(ok)

        if panel_id and keypad_id and site_id:
            # Alarm panels and keypads attach to an alarm system, which
            # must be created first. The keypad step needs the system id.
            ok, alarm_system_id = await step(
                "Creating alarm system",
                client.create_alarm_system,
                site_id,
            )
            track(ok)

            if alarm_system_id:
                ok, _ = await step(
                    "Configuring alarm panel",
                    client.configure_alarm_panel,
                    panel_id,
                    AS_PANEL_NAME,
                    alarm_system_id,
                )
                track(ok)

                ok, _ = await step(
                    "Configuring alarm keypad",
                    client.configure_keypad,
                    keypad_id,
                    AS_KEYPAD_NAME,
                    alarm_system_id,
                    keypad_serial,
                )
                track(ok)

                ok, _ = await step(
                    "Setting up general keycode",
                    client.set_alarm_keycode,
                    alarm_system_id,
                )
                track(ok)

    # ------------------------------------------------------------------
    # Supporting steps
    # ------------------------------------------------------------------

    async def _invite_supporting_users(self, step, track, client, role: str) -> None:
        """Walk the user rows and invite each one with non-empty fields."""
        for control in self._users_column.controls:
            if not isinstance(control, ft.Row):
                continue  # only ft.Row instances are added by _create_user_row
            row: ft.Row = control
            fields = [c for c in row.controls if isinstance(c, ft.TextField)]
            if len(fields) < 3:
                continue
            first = (fields[0].value or "").strip()
            last = (fields[1].value or "").strip()
            email_val = (fields[2].value or "").strip()
            if not (first and last and email_val):
                continue
            ok, _ = await step(
                f"Adding user {first} {last}",
                client.invite_user,
                email_val,
                first,
                last,
                role,
            )
            track(ok)

    # ------------------------------------------------------------------
    # UI helpers used by the orchestrator
    # ------------------------------------------------------------------

    def _progress_note(self, page, text: str) -> None:
        """
        Append a gray italic note to the progress column. Used for
        "Waiting for X..." messages that aren't backed by an API call and
        therefore don't go through _run_step.
        """
        self._progress_column.controls.append(
            ft.Text(text, color=TEXT_SECONDARY, size=12)
        )
        page.update()

    def _render_summary(self, page, all_success: bool) -> None:
        """Run -> Report: a structured result with failures surfaced first.

        Branches on the cancel token so a user-aborted run shows a clear
        "Cancelled" header instead of the success/partial-success line.
        """
        self._stepper.set_active(3)

        cancelled = bool(self._cancel_token and self._cancel_token.is_cancelled)
        if cancelled:
            kind = "warning"
            message = "Commission cancelled."
            bar_color = WARNING
        elif all_success:
            kind = "success"
            message = f"Commission complete — {self._steps_done} steps, 0 failed."
            bar_color = SECONDARY
        else:
            kind = "warning"
            message = (
                f"Commission completed with errors — {self._steps_done} done, "
                f"{self._steps_failed} failed."
            )
            bar_color = WARNING

        self.cancel_btn.visible = False
        self._progress_header.set_progress(
            self._steps_done, failed=self._steps_failed
        )
        self._progress_header.complete(color=bar_color)

        # Hide the live chronological step list behind the raw-log disclosure;
        # the report leads with the outcome and any failures.
        self._progress_column.visible = False

        report: list[ft.Control] = [banner(message, kind=kind)]

        if self._failures:
            failure_rows = [
                status_row("failed", label, detail=err)
                for label, err in self._failures
            ]
            report.append(ft.Container(height=8))
            report.append(
                section_header(
                    "Failed steps", f"{len(self._failures)} step(s) need attention"
                )
            )
            report.extend(failure_rows)

        report.append(ft.Container(height=8))
        report.append(RawLogPanel(lambda: "\n".join(self._run_log) or "(no steps)"))
        report.append(ft.Container(height=12))
        report.append(
            ft.Row(
                [
                    ft.OutlinedButton(
                        content=ft.Text("Copy log", color=TEXT_SECONDARY),
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, BORDER),
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                        height=42,
                        on_click=self._on_copy_log,
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Export report (CSV)", color=TEXT_SECONDARY),
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, BORDER),
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                        height=42,
                        on_click=self._on_export_report,
                    ),
                    ft.ElevatedButton(
                        content=ft.Text(
                            "Return to Home",
                            color=TEXT_PRIMARY,
                            weight=ft.FontWeight.W_600,
                        ),
                        bgcolor=SECONDARY,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8)
                        ),
                        height=42,
                        on_click=lambda _: self.push_route("/home"),
                    ),
                ],
                spacing=10,
            )
        )
        self._run_section.controls.append(
            ft.Column(report, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        )
        page.update()

    async def _on_copy_log(self, e):
        try:
            await e.page.clipboard.set("\n".join(self._run_log))
            show_toast(e.page, "Run log copied to clipboard.", kind="success")
        except Exception:
            show_toast(e.page, "Couldn't access the clipboard.", kind="warning")

    def _on_export_report(self, e):
        rows = [
            {
                "Step": label,
                "Result": "FAILED",
                "Detail": err,
            }
            for label, err in self._failures
        ]
        # Include the full chronological log so a clean run still exports.
        for line in self._run_log:
            result = "FAILED" if line.startswith("[FAIL]") else "OK"
            rows.append({"Step": line, "Result": result, "Detail": ""})
        try:
            path = export_csv(
                rows, ["Step", "Result", "Detail"], "commission_report"
            )
            show_toast(e.page, f"Report saved to {path}", kind="success", duration_ms=4000)
        except Exception as ex:
            show_alert(e.page, "Export Failed", str(ex))

    def _on_cancel(self, e):
        """Cancel button: trip the token and disable further clicks.

        The in-flight API call is allowed to finish; the next step sees
        the token and renders as 'skipped (cancelled)'.
        """
        if self._cancel_token is None:
            return
        self._cancel_token.cancel()
        self.cancel_btn.disabled = True
        if isinstance(self.cancel_btn.content, ft.Text):
            self.cancel_btn.content.value = "Cancelling..."
        self._progress_note(
            e.page,
            "Cancelling — the current step will finish, then commission will stop.",
        )

    async def _run_step(self, page, loop, label: str, fn, *args) -> tuple[bool, object]:
        """
        Run a single commissioning step in the executor with UI feedback.

        Renders a spinner+label row, awaits the function (which should be a
        sync callable from the API clients — it will be offloaded to the
        thread executor), then swaps the spinner for a check or error icon.

        Returns (ok, result). On failure result is None and the exception
        text is shown in the row. When the cancel token has been tripped,
        the step is skipped (renders as a grey "cancelled" row) and
        returns (False, None) so the flow records it but moves on.
        """
        if self._cancel_token and self._cancel_token.is_cancelled:
            cancelled_row = ft.Row(
                [
                    ft.Icon(ft.Icons.CANCEL, color=WARNING, size=18),
                    ft.Text(
                        f"{label} — skipped (cancelled)",
                        color=WARNING,
                        size=13,
                    ),
                ],
                spacing=10,
            )
            self._progress_column.controls.append(cancelled_row)
            page.update()
            return False, None

        step_icon = ft.ProgressRing(
            width=16, height=16, stroke_width=2, color=TEXT_SECONDARY
        )
        step_text = ft.Text(f"{label}...", color=TEXT_SECONDARY, size=13)
        step_row = ft.Row([step_icon, step_text], spacing=10)
        self._progress_column.controls.append(step_row)
        page.update()
        await asyncio.sleep(0)

        try:
            result = await loop.run_in_executor(_executor, fn, *args)
            step_row.controls[0] = ft.Icon(
                ft.Icons.CHECK_CIRCLE, color=SECONDARY, size=18
            )
            step_text.value = f"{label} — done"
            step_text.color = SECONDARY
            self._steps_done += 1
            self._run_log.append(f"[ok]   {label}")
            self._progress_header.set_progress(
                self._steps_done, failed=self._steps_failed
            )
            page.update()
            return True, result
        except Exception as ex:
            step_row.controls[0] = ft.Icon(ft.Icons.ERROR, color=ERROR, size=18)
            step_text.value = f"{label} — failed: {ex}"
            step_text.color = ERROR
            self._steps_failed += 1
            self._failures.append((label, str(ex)))
            self._run_log.append(f"[FAIL] {label}: {ex}")
            self._progress_header.set_progress(
                self._steps_done, failed=self._steps_failed
            )
            page.update()
            return False, None
