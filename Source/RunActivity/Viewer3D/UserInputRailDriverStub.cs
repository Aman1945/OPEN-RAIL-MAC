// Stub for the RailDriver USB hardware controller on platforms where the
// Windows-only RailDriver driver/package is unavailable (e.g. macOS/Linux).
using Orts.Viewer3D.Processes;

namespace Orts.Viewer3D
{
    public class RailDriverState : ExternalDeviceState
    {
        public RailDriverState(Game game)
        {
        }

        public void Update()
        {
        }

        public void Activate()
        {
        }

        public void ShowSpeed(float speed)
        {
        }

        public void Shutdown()
        {
        }
    }
}
