# Robo Architect NSIS entrypoint.
#
# electron-builder normally compiles and executes a temporary unsigned
# installer so it can extract and optionally sign the uninstaller before the
# final build. Enterprise Windows App Control can block that intermediate
# execution. This version keeps electron-builder's standard install flow but
# writes the uninstaller directly during installation.

Var newStartMenuLink
Var oldStartMenuLink
Var newDesktopLink
Var oldDesktopLink
Var oldShortcutName
Var oldMenuDirectory

!include "common.nsh"
!include "MUI2.nsh"
!include "multiUser.nsh"
!include "allowOnlyOneInstallerInstance.nsh"

!ifdef INSTALL_MODE_PER_ALL_USERS
  RequestExecutionLevel admin
!else
  RequestExecutionLevel user
!endif

Var appExe
Var launchLink

!ifdef ONE_CLICK
  !include "oneClick.nsh"
!else
  !include "assistedInstaller.nsh"
!endif

!insertmacro addLangs

!ifmacrodef customHeader
  !insertmacro customHeader
!endif

# installApplicationFiles expects an already-built uninstaller. Give it a
# harmless placeholder that customInstall replaces immediately.
!ifdef UNINSTALLER_OUT_FILE
  !undef UNINSTALLER_OUT_FILE
!endif
!define UNINSTALLER_OUT_FILE "${MUI_ICON}"

!macro customInstall
  WriteUninstaller "$INSTDIR\${UNINSTALL_FILENAME}"
!macroend

Function .onInit
  Call setInstallSectionSpaceRequired

  SetOutPath $INSTDIR
  ${LogSet} on

  !ifmacrodef preInit
    !insertmacro preInit
  !endif

  !ifdef DISPLAY_LANG_SELECTOR
    !insertmacro MUI_LANGDLL_DISPLAY
  !endif

  !insertmacro check64BitAndSetRegView

  !ifdef ONE_CLICK
    !insertmacro ALLOW_ONLY_ONE_INSTALLER_INSTANCE
  !else
    ${IfNot} ${UAC_IsInnerInstance}
      !insertmacro ALLOW_ONLY_ONE_INSTALLER_INSTANCE
    ${EndIf}
  !endif

  !insertmacro initMultiUser

  !ifmacrodef customInit
    !insertmacro customInit
  !endif

  !ifmacrodef addLicenseFiles
    InitPluginsDir
    !insertmacro addLicenseFiles
  !endif
FunctionEnd

!include "installUtil.nsh"

Section "install" INSTALL_SECTION_ID
  # If a silent upgrade targets an existing per-machine installation, elevate
  # before extracting the new application.
  !ifndef INSTALL_MODE_PER_ALL_USERS
    !ifndef ONE_CLICK
      ${if} $hasPerMachineInstallation == "1"
      ${andIf} ${Silent}
        ${ifNot} ${UAC_IsAdmin}
          ShowWindow $HWNDPARENT ${SW_HIDE}
          !insertmacro UAC_RunElevated
          ${Switch} $0
            ${Case} 0
              ${Break}
            ${Case} 1223
              ${Break}
            ${Default}
              MessageBox mb_IconStop|mb_TopMost|mb_SetForeground "Unable to elevate, error $0"
              ${Break}
          ${EndSwitch}
          Quit
        ${else}
          !insertmacro setInstallModePerAllUsers
        ${endIf}
      ${endIf}
    !endif
  !endif

  !include "installSection.nsh"
SectionEnd

Function setInstallSectionSpaceRequired
  !insertmacro setSpaceRequired ${INSTALL_SECTION_ID}
FunctionEnd

Function un._GetProcessInfo
  !insertmacro FUNC_GETPROCESSINFO
FunctionEnd

!define BUILD_UNINSTALLER
!include "uninstaller.nsh"
!undef BUILD_UNINSTALLER
